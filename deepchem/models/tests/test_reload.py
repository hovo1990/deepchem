"""
Test reload for trained models.
"""
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

__author__ = "Bharath Ramsundar"
__copyright__ = "Copyright 2016, Stanford University"
__license__ = "GPL"

import unittest
import tempfile
import numpy as np
import deepchem as dc
import tensorflow as tf
from keras import backend as K
from sklearn.ensemble import RandomForestClassifier

class TestReload(unittest.TestCase):

  def test_sklearn_reload(self):
    """Test that trained model can be reloaded correctly."""
    n_samples = 10
    n_features = 3
    n_tasks = 1 
    
    # Generate dummy dataset
    np.random.seed(123)
    ids = np.arange(n_samples)
    X = np.random.rand(n_samples, n_features)
    y = np.random.randint(2, size=(n_samples, n_tasks))
    w = np.ones((n_samples, n_tasks))
  
    dataset = dc.data.NumpyDataset(X, y, w, ids)
    classification_metric = dc.metrics.Metric(dc.metrics.roc_auc_score)

    sklearn_model = RandomForestClassifier()
    model_dir = tempfile.mkdtemp()
    model = dc.models.SklearnModel(sklearn_model, model_dir)

    # Fit trained model
    model.fit(dataset)
    model.save()

    # Load trained model
    reloaded_model = dc.models.SklearnModel(None, model_dir)
    reloaded_model.reload()

    # Eval model on train
    scores = reloaded_model.evaluate(dataset, [classification_metric])
    assert scores[classification_metric.name] > .9

  def test_keras_reload(self):
    """Test that trained keras models can be reloaded correctly."""
    g = tf.Graph()
    sess = tf.Session(graph=g)
    K.set_session(sess)
    with g.as_default():
      n_samples = 10
      n_features = 3
      n_tasks = 1
      
      # Generate dummy dataset
      np.random.seed(123)
      ids = np.arange(n_samples)
      X = np.random.rand(n_samples, n_features)
      y = np.random.randint(2, size=(n_samples, n_tasks))
      w = np.ones((n_samples, n_tasks))
    
      dataset = dc.data.NumpyDataset(X, y, w, ids)

      classification_metric = dc.metrics.Metric(dc.metrics.roc_auc_score)
      keras_model = dc.models.MultiTaskDNN(
          n_tasks, n_features, "classification", dropout=0.)
      model_dir = tempfile.mkdtemp()
      model = dc.models.KerasModel(keras_model, model_dir)

      # Fit trained model
      model.fit(dataset)
      model.save()

      # Load trained model
      reloaded_keras_model = dc.models.MultiTaskDNN(
          n_tasks, n_features, "classification", dropout=0.)
      reloaded_model = dc.models.KerasModel(reloaded_keras_model, model_dir)
      reloaded_model.reload(
          custom_objects={"MultiTaskDNN": dc.models.MultiTaskDNN})

      # Eval model on train
      scores = reloaded_model.evaluate(dataset, [classification_metric])
      assert scores[classification_metric.name] > .6

  def test_tf_reload(self):
    """Test that tensorflow models can overfit simple classification datasets."""
    n_samples = 10
    n_features = 3
    n_tasks = 1 
    n_classes = 2
    
    # Generate dummy dataset
    np.random.seed(123)
    ids = np.arange(n_samples)
    X = np.random.rand(n_samples, n_features)
    y = np.random.randint(n_classes, size=(n_samples, n_tasks))
    w = np.ones((n_samples, n_tasks))
  
    dataset = dc.data.NumpyDataset(X, y, w, ids)

    classification_metric = dc.metrics.Metric(dc.metrics.accuracy_score)

    model_dir = tempfile.mkdtemp()
    model = dc.models.TensorflowMultiTaskClassifier(
          n_tasks, n_features, model_dir, dropouts=[0.], verbosity="high")

    # Fit trained model
    model.fit(dataset)
    model.save()

    # Load trained model
    reloaded_model = dc.models.TensorflowMultiTaskClassifier(
        n_tasks, n_features, model_dir, dropouts=[0.],
        verbosity="high")
    reloaded_model.reload()

    # Eval model on train
    scores = reloaded_model.evaluate(dataset, [classification_metric])
    assert scores[classification_metric.name] > .6
