#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 18 15:53:27 2016

@author: Michael Wu

Benchmark test
Giving performances of RF(scikit) and MultitaskDNN(TF)
on datasets: muv, nci, pcba, tox21

time estimation(on a nvidia tesla K20 GPU):
tox21   - dataloading: 30s
        - tf: 40s
muv     - dataloading: 400s
        - tf: 250s
pcba    - dataloading: 30min
        - tf: 2h
sider   - dataloading: 10s
        - tf: 60s
toxcast - dataloading: 70s
        - tf: 40min
(will include more)

Total time of running a benchmark test: 3~4h
"""
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import sys
import os
import numpy as np
import shutil
import time
import deepchem as dc
import tensorflow as tf
from keras import backend as K

from sklearn.ensemble import RandomForestClassifier

from muv.muv_datasets import load_muv
from nci.nci_datasets import load_nci
from pcba.pcba_datasets import load_pcba
from tox21.tox21_datasets import load_tox21
from toxcast.toxcast_datasets import load_toxcast
from sider.sider_datasets import load_sider

def benchmark_loading_datasets(base_dir_o, hyper_parameters, 
                               dataset_name='all',model='tf',reload = True,
                               verbosity='high', out_path='/tmp'):
  """
  Loading dataset for benchmark test
  
  Parameters
  ----------
  base_dir_o : string
      path of working folder, will be combined with '/dataset_name'
  
  hyper_parameters : dict of list
      hyper parameters including dropout rate, learning rate, etc.
  
  dataset_name : string, optional (default='all')
      choice of which dataset to use, 'all' = computing all the datasets
      
  model : string,  optional (default='tf')
      choice of which model to use, should be: tf, logreg, graphconv
  
  out_path : string, optional(default='/tmp')
      path of result file
      
  """
  if not dataset_name in ['all','muv','nci','pcba','tox21','sider','toxcast']:
    raise ValueError('Dataset not supported')
                          
  if model in ['graphconv']:
    featurizer = 'GraphConv'
    n_features = 71
  elif model in ['tf', 'tf_robust', 'logreg', 'rf']:
    featurizer = 'ECFP'
    n_features = 1024
  else:
    raise ValueError('Model not supported')
      
  if dataset_name == 'all':
    #currently not including the nci dataset
    dataset_name = ['tox21','muv','pcba','sider','toxcast']
  else:
    dataset_name = [dataset_name]
  
  loading_functions = {'tox21': load_tox21, 'muv': load_muv,
                       'pcba': load_pcba, 'nci': load_nci,
                       'sider': load_sider, 'toxcast': load_toxcast}
  
  for dname in dataset_name:
    print('-------------------------------------')
    print('Benchmark %s on dataset: %s' % (model, dname))
    print('-------------------------------------')
    base_dir = os.path.join(base_dir_o, dname)
    
    time_start = time.time()
    #loading datasets     
    tasks, datasets, transformers = loading_functions[dname](
        featurizer=featurizer)
    train_dataset, valid_dataset, test_dataset = datasets
    time_finish_loading = time.time()
    #time_finish_loading-time_start is the time(s) used for dataset loading
    

    #running model
    for count, hp in enumerate(hyper_parameters[model]):
      time_start_fitting = time.time()
      train_score,valid_score = benchmark_train_and_valid(base_dir,
                                    train_dataset, valid_dataset, tasks,
                                    transformers, hp, n_features,
                                    model=model,verbosity = verbosity)      
      time_finish_fitting = time.time()
      
      with open(os.path.join(out_path, 'results.csv'),'a') as f:
        f.write('\n\n'+str(count))
        f.write('\n'+dname+',train')
        for i in train_score:
          f.write(','+i+','+str(train_score[i]['mean-roc_auc_score']))
        f.write('\n'+dname+',valid')
        for i in valid_score:
          f.write(','+i+','+str(valid_score[i]['mean-roc_auc_score'])) 
        f.write('\n'+dname+',time_for_running,'+
              str(time_finish_fitting-time_start_fitting))

    #clear workspace         
    del tasks,datasets,transformers
    del train_dataset,valid_dataset, test_dataset
    del time_start,time_finish_loading,time_start_fitting,time_finish_fitting

  return None

def benchmark_train_and_valid(base_dir, train_dataset, valid_dataset, tasks,
                              transformers, hyper_parameters,
                              n_features, model='tf', seed=123,
                              verbosity='high'):
  """
  Calculate performance of different models on the specific dataset & tasks
  
  Parameters
  ----------
  base_dir : string
      path of working folder
      
  train_dataset : dataset struct
      loaded dataset using load_* or splitter function
      
  valid_dataset : dataset struct
      loaded dataset using load_* or splitter function
  
  tasks : list of string
      list of targets(tasks, datasets)
  
  transformers : BalancingTransformer struct
      loaded properties of dataset from load_* function
  
  hyper_parameters : dict of list
      hyper parameters including dropout rate, learning rate, etc.
 
  n_features : integer, optional (default=1024)
      number of features, or length of binary fingerprints
  
  model : string, optional (default='all')
      choice of which model to use, 'all' = running all models on the dataset
  

  Returns
  -------
  train_scores : dict
	predicting results(AUC, R2) on training set
  valid_scores : dict
	predicting results(AUC, R2) on valid set

  """
  train_scores = {}
  valid_scores = {}
  
  # Initialize metrics
  classification_metric = dc.metrics.Metric(dc.metrics.roc_auc_score, np.mean,
                                            verbosity=verbosity,
                                            mode="classification")
  
  assert model in ['graphconv', 'tf', 'tf_robust', 'rf','logreg']

  if model == 'tf':
    # Building tensorflow MultiTaskDNN model
    dropouts = hyper_parameters['dropouts']
    learning_rate = hyper_parameters['learning_rate']
    layer_sizes = hyper_parameters['layer_sizes']
    batch_size = hyper_parameters['batch_size']
    nb_epoch = hyper_parameters['nb_epoch']

    model_tf = dc.models.TensorflowMultiTaskClassifier(
          len(tasks), n_features, learning_rate=learning_rate,
          layer_sizes=layer_sizes, dropouts=dropouts, batch_size=batch_size, 
          seed=seed, verbosity=verbosity)
 
    print('-------------------------------------')
    print('Start fitting by tensorflow')
    model_tf.fit(train_dataset,nb_epoch = nb_epoch)
    
    train_scores['tensorflow'] = model_tf.evaluate(
        train_dataset, [classification_metric], transformers)

    valid_scores['tensorflow'] = model_tf.evaluate( 
        valid_dataset, [classification_metric], transformers)

  if model == 'tf_robust':
    # Building tensorflow MultiTaskDNN model
    dropouts = hyper_parameters['dropouts']
    bypass_dropouts = hyper_parameters['bypass_dropouts']
    learning_rate = hyper_parameters['learning_rate']
    layer_sizes = hyper_parameters['layer_sizes']
    bypass_layer_sizes = hyper_parameters['bypass_layer_sizes']
    batch_size = hyper_parameters['batch_size']
    nb_epoch = hyper_parameters['nb_epoch']

    model_robust = dc.models.RobustMultitaskClassifier(
        len(tasks), n_features, learning_rate=learning_rate,
        layer_sizes=layer_sizes, bypass_layer_sizes=bypass_layer_sizes,
        dropouts=dropouts, bypass_dropouts=bypass_dropouts, 
        batch_size=batch_size, seed=seed, verbosity=verbosity)
 
    print('-------------------------------------')
    print('Start fitting by tensorflow')
    model_robust.fit(train_dataset,nb_epoch = nb_epoch)
    
    train_scores['tf_robust'] = model_robust.evaluate(
        train_dataset, [classification_metric], transformers)

    valid_scores['tf_robust'] = model_robust.evaluate( 
        valid_dataset, [classification_metric], transformers)


  if model == 'logreg':
    # Building tensorflow logistic regression model
    learning_rate = hyper_parameters['learning_rate']
    penalty = hyper_parameters['penalty']
    penalty_type = hyper_parameters['penalty_type']
    batch_size = hyper_parameters['batch_size']
    nb_epoch = hyper_parameters['nb_epoch']

    model_logreg = dc.models.TensorflowLogisticRegression(
          len(tasks), n_features, learning_rate=learning_rate, penalty=penalty, 
          penalty_type=penalty_type, batch_size=batch_size, 
          seed=seed, verbosity=verbosity)
 
    print('-------------------------------------')
    print('Start fitting by logistic regression')
    model_logreg.fit(train_dataset,nb_epoch = nb_epoch)
    
    train_scores['logreg'] = model_logreg.evaluate(train_dataset,
                               [classification_metric],transformers)

    valid_scores['logreg'] = model_logreg.evaluate(valid_dataset,
                               [classification_metric],transformers)

  if model == 'graphconv':
    # Initialize model folder
    model_dir_graphconv = os.path.join(base_dir, "model_graphconv")
    
    
    learning_rate = hyper_parameters['learning_rate']
    n_filters = hyper_parameters['n_filters']
    n_fully_connected_nodes = hyper_parameters['n_fully_connected_nodes']
    batch_size = hyper_parameters['batch_size']
    nb_epoch = hyper_parameters['nb_epoch']
    
    g = tf.Graph()
    sess = tf.Session(graph=g)
    K.set_session(sess)
    with g.as_default():
      tf.set_random_seed(seed)
      graph_model = dc.nn.SequentialGraph(n_features)
      graph_model.add(dc.nn.GraphConv(int(n_filters), activation='relu'))
      graph_model.add(dc.nn.BatchNormalization(epsilon=1e-5, mode=1))
      graph_model.add(dc.nn.GraphPool())
      graph_model.add(dc.nn.GraphConv(int(n_filters), activation='relu'))
      graph_model.add(dc.nn.BatchNormalization(epsilon=1e-5, mode=1))
      graph_model.add(dc.nn.GraphPool())
      # Gather Projection
      graph_model.add(dc.nn.Dense(int(n_fully_connected_nodes),
                                  activation='relu'))
      graph_model.add(dc.nn.BatchNormalization(epsilon=1e-5, mode=1))
      graph_model.add(dc.nn.GraphGather(batch_size, activation="tanh"))
      with tf.Session() as sess:
        model_graphconv = dc.models.MultitaskGraphClassifier(
          sess, graph_model, len(tasks), model_dir_graphconv, 
          batch_size=batch_size, learning_rate=learning_rate,
          optimizer_type="adam", beta1=.9, beta2=.999, verbosity="high")

        # Fit trained model
        model_graphconv.fit(train_dataset, nb_epoch=nb_epoch)
    
        train_scores['graphconv'] = model_graphconv.evaluate(train_dataset,
                               [classification_metric],transformers)

        valid_scores['graphconv'] = model_graphconv.evaluate(valid_dataset,
                               [classification_metric],transformers)
    
  if model == 'rf':
    # Initialize model folder
    model_dir_rf = os.path.join(base_dir, "model_rf")
    
    n_estimators = hyper_parameters['n_estimators']

    # Building scikit random forest model
    def model_builder(model_dir_rf):
      sklearn_model = RandomForestClassifier(
        class_weight="balanced", n_estimators=n_estimators,n_jobs=-1)
      return dc.models.sklearn_models.SklearnModel(sklearn_model, model_dir_rf)
    model_rf = dc.models.multitask.SingletaskToMultitask(
		tasks, model_builder, model_dir_rf)
    
    print('-------------------------------------')
    print('Start fitting by random forest')
    model_rf.fit(train_dataset)
    train_scores['random_forest'] = model_rf.evaluate(train_dataset,
                                    [classification_metric],transformers)

    valid_scores['random_forest'] = model_rf.evaluate(valid_dataset,
                                    [classification_metric],transformers)

  return train_scores, valid_scores

if __name__ == '__main__':
  # Global variables
  np.random.seed(123)
  verbosity = 'high'
  
  #Working folder initialization
  base_dir_o="/tmp/benchmark_test_"+time.strftime("%Y_%m_%d", time.localtime())
  if os.path.exists(base_dir_o):
    shutil.rmtree(base_dir_o)
  os.makedirs(base_dir_o)
  
  #Datasets and models used in the benchmark test, all=all the datasets
  dataset_name = 'muv'
  model = 'tf'

  #input hyperparameters
  #tf: dropouts, learning rate, layer_sizes, weight initial stddev,penalty,
  #    batch_size
  hps = {}
  hps['tf'] = [{'dropouts': [0.25], 'learning_rate': 0.001,
                'layer_sizes': [1000], 'batch_size': 50, 'nb_epoch': 10}]

  hps['tf_robust'] = [{'dropouts': [0.5], 'bypass_dropouts': [0.5],
                       'learning_rate': 0.001,
                       'layer_sizes': [500], 'bypass_layer_sizes': [100],
                       'batch_size': 50, 'nb_epoch': 10}]
                
  hps['logreg'] = [{'learning_rate': 0.001, 'penalty': 0.05, 
                    'penalty_type': 'l1', 'batch_size': 50, 'nb_epoch': 10}]
                
  hps['graphconv'] = [{'learning_rate': 0.001, 'n_filters': 64,
                       'n_fully_connected_nodes': 128, 'batch_size': 50,
                       'nb_epoch': 10}]
  
  hps['rf'] = [{'n_estimators': 500}]
                
  benchmark_loading_datasets(base_dir_o, hps, dataset_name=dataset_name,
                             model=model, reload=reload, verbosity='high')
