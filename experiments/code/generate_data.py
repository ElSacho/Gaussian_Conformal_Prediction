import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from scipy.stats import special_ortho_group
from scipy.spatial.transform import Rotation as R
from scipy.linalg import cholesky
from scipy.linalg import logm, expm
from utils import KMeans
from utils import seed_everything


def interpolate_rotations(tab_matrix, weights):
    """
    Interpolates between multiple orthogonal rotation matrices of size \( k \times k \).

    Arguments:
    - tab_matrix: list or array of np.ndarray with shape (n, k, k),
    where each matrix is an orthogonal rotation matrix.
    - weights: list or array of shape (n,), weights associated with each matrix.

    Returns:
    - Interpolated rotation matrix (np.ndarray of shape (k, k)).
    """
    tab_matrix = np.array(tab_matrix)
    weights = np.array(weights)
    
    assert tab_matrix.shape[1] == tab_matrix.shape[2], "Matrices must be square."
    assert len(weights) == tab_matrix.shape[0], "Weights must match the number of matrices."
    
    # Normalize the weights
    weights = weights / np.sum(weights)

    # Compute the weighted logarithm
    log_sum = np.zeros_like(tab_matrix[0])
    for mat, w in zip(tab_matrix, weights):
        log_sum += w * logm(mat)  # Add the weighted logarithm

    # Return to the space of rotations with the exponential
    interpolated_matrix = expm(log_sum)
    return interpolated_matrix

class NonLinearFunction:
    def __init__(self, d, k, beta=None):
        if beta is None:
            beta = np.random.randn(d, k)
        self.beta = beta

    def get(self, x):
        nonlinear_term = np.sin(np.dot(x, self.beta)) + 0.5 * np.tanh(np.dot(x**2, self.beta))
        return nonlinear_term 
    
class NonLinearFunctionUselessFeatures:
    def __init__(self, d, k, number_usefull_features=5, beta=None):
        if beta is None:
            beta = np.random.randn(number_usefull_features, k)
        self.beta = beta
        self.number_usefull_features = number_usefull_features

    def get(self, x):
        x_usefull = x[:, :self.number_usefull_features]
        nonlinear_term = np.sin(np.dot(x_usefull, self.beta)) + 0.5 * np.tanh(np.dot(x_usefull**2, self.beta))
        return nonlinear_term
    
class RadiusTransformation:
    def __init__(self, d, beta=None):
        if beta is None:
            beta = np.random.randn(d)
        self.beta = beta

    def get(self, x):
        return ( np.linalg.norm(x) + 10.0 ) / 10
    
class IdTransformation:
    def __init__(self, d, beta=None):
        if beta is None:
            beta = np.random.randn(d)
        self.beta = beta

    def get(self, x):
        return 1.0
    

class LocalPerturbation:
    def __init__(self, d, k, n_anchors=4, radius_transformation=None, seed=42):
        seed_everything(seed)
        self.k = k
        if radius_transformation is not None:
            self.radius_transformation = radius_transformation
        else : self.radius_transformation = IdTransformation(d)
        self.k  = k
        if self.k == 1: return 

        self.anchors_mu = []
        self.anchors_cov = []
        random_points = np.random.randn(1000, d)
        kmeans = KMeans(n_clusters=n_anchors, random_state=seed)
        kmeans.fit(random_points)
        centers = kmeans.centroids
        for i in range(n_anchors):
            self.anchors_mu.append(centers[i])
            covariance_matrix = special_ortho_group.rvs(dim=k)
            self.anchors_cov.append(covariance_matrix)
              
    def inverse_distance(self, point1, point2):
        return (1 / (np.linalg.norm(point1 - point2) + 1e-6)) ** 4

    def get_one_x(self, x):
        if self.k == 1:
            return np.array(self.radius_transformation.get(x)).reshape(1, 1)
            
        sum_inv_dist = np.sum([self.inverse_distance(x, mu) for mu in self.anchors_mu])
        weights = [self.inverse_distance(x, mu) / sum_inv_dist for mu in self.anchors_mu]
        cov = interpolate_rotations(self.anchors_cov, weights)
        cov = cov * self.radius_transformation.get(x)
        return cov
    
    def get(self, x):
        return np.array([ self.get_one_x(x_i) for x_i in x])
    

class LocalPerturbationPSD:
    def __init__(self, d, k, n_anchors=4, radius_transformation=None):
        self.k = k
        if radius_transformation is not None:
            self.radius_transformation = radius_transformation
        else : self.radius_transformation = IdTransformation(d)
        self.k  = k
        if self.k == 1: return 

        self.anchors_mu = []
        self.anchors_cov = []
        random_points = np.random.randn(1000, d)
        kmeans = KMeans(n_clusters=n_anchors)
        kmeans.fit(random_points)
        centers = kmeans.centroids
        for i in range(n_anchors):
            self.anchors_mu.append(centers[i])
            mat_A = np.random.randn(k, k)
            covariance_matrix = np.dot(mat_A.T, mat_A)
            self.anchors_cov.append(covariance_matrix)
        if n_anchors == 2:
            self.anchors_mu.append(centers[i])
            self.anchors_cov = [np.array([1, -0.9, -0.9, 1]).reshape(2, 2), np.array([1, 0.9, 0.9, 1]).reshape(2, 2)]
        
    def inverse_distance(self, point1, point2):
        return (1 / (np.linalg.norm(point1 - point2) + 1e-6)) ** 4

    def get_one_x(self, x):
        if self.k == 1:
            return self.radius_transformation.get(x)
            
        sum_inv_dist = np.sum([self.inverse_distance(x, mu) for mu in self.anchors_mu])
        cov = np.sum([self.inverse_distance(x, mu) / sum_inv_dist * cov for mu, cov in zip(self.anchors_mu, self.anchors_cov)], axis=0)
        return cholesky(cov)
    
    def get(self, x):
        return np.array([ self.get_one_x(x_i) for x_i in x])

class LocalPerturbationBin:
    def __init__(self, d, k, n_anchors=4):
        self.k = k
        self.anchors_mu = []
        self.anchors_cov = []
        random_points = np.random.randn(1000, d)
        kmeans = KMeans(n_clusters=n_anchors)
        kmeans.fit(random_points)
        centers = kmeans.centroids
        for i in range(n_anchors):
            self.anchors_mu.append(centers[i])
            mat_A = np.random.randn(k, k)
            covariance_matrix = np.dot(mat_A.T, mat_A)
            self.anchors_cov.append(covariance_matrix)
        if n_anchors == 2:
            self.anchors_mu.append(centers[i])
            self.anchors_cov = [np.array([1, -0.9, -0.9, 1]).reshape(2, 2), np.array([1, 0.9, 0.9, 1]).reshape(2, 2)]


    def inverse_distance(self, point1, point2):
        return (1 / (np.linalg.norm(point1 - point2) + 1e-6)) ** 4

    def get_one_x(self, x):
        idx = np.argmax([self.inverse_distance(x, mu) for mu in self.anchors_mu])
        cov = self.anchors_cov[idx]
        return cholesky(cov)
    
    def get(self, x):
        return np.array([self.get_one_x(x_i) for x_i in x])




class LinearFunction:
    def __init__(self, d, k, beta=None):
        if beta is None:
            beta = np.random.randn(d, k)
        self.beta = beta

    def get(self, x):
        return np.dot(x, self.beta)
    
class Perturbation:
    def __init__(self, k, noise_type, scale_noise= 1.0, covariance_matrix=None):
        self.scale_noise = scale_noise
        self.noise_type = noise_type
        self.k = k
        if covariance_matrix is not None:
            self.covariance_matrix = covariance_matrix
        else:
            A = np.random.randn(k, k)
            self.covariance_matrix = A @ A.T

    def get(self, x):
        n = x.shape[0]
        data_perturbation = self.scale_noise * get_perturbation(self.noise_type, n, self.k, covariance_matrix=self.covariance_matrix)
        return data_perturbation

class DataGenerator:
    def __init__(self, input_dim, output_dim, noise_type, f_star=None, scale_noise = 1.0, local_perturbation = None, law_x = "gaussian", covariance_matrix = None, bias=True, seed = 42):
        seed_everything(seed)
        self.perturbation = Perturbation(output_dim, noise_type, scale_noise=scale_noise, covariance_matrix=covariance_matrix)
        self.local_perturbation = local_perturbation
        self.law_x = law_x
        if f_star is None:
            self.f_star = LinearFunction(input_dim, output_dim)
        else:
            self.f_star = f_star
        self.d = input_dim
        self.k = output_dim
        self.bias = bias
        self.noise_type = noise_type
        self.covariance_matrix = covariance_matrix

    def process(self, x_train, y_train, x_test, y_test, x_cal, y_cal):

        # Compute statistics from the training set
        self.x_mean = x_train.mean(axis=0)
        self.x_range = x_train.max(axis=0) - x_train.min(axis=0)
        
        self.y_mean = y_train.mean(axis=0)
        self.y_range = y_train.max(axis=0) - y_train.min(axis=0)

        # Normalize the datasets
        x_train_processed = (x_train - self.x_mean) / self.x_range
        x_test_processed = (x_test - self.x_mean) / self.x_range
        x_cal_processed = (x_cal - self.x_mean) / self.x_range
        
        y_train_processed = (y_train - self.y_mean) / self.y_range
        y_test_processed = (y_test - self.y_mean) / self.y_range
        y_cal_processed = (y_cal - self.y_mean) / self.y_range
        
        return x_train_processed, y_train_processed, x_test_processed, y_test_processed, x_cal_processed, y_cal_processed

    def process_from_train(self, x_specific, y_specific):
        # Normalize the datasets
        x_train_processed = (x_specific - self.x_mean) / self.x_range
        y_train_processed = (y_specific - self.y_mean) / self.y_range
        
        return x_train_processed, y_train_processed

    def generate_specific_x(self, n):
        if self.bias:
            x_specific = get_perturbation(self.law_x, 1, self.d-1, covariance_matrix=np.eye(self.d-1))
            x_specific = np.repeat(x_specific, n, axis=0)
            x_specific = np.hstack([np.ones((n, 1)), x_specific])
        else:
            x_specific = get_perturbation(self.law_x, 1, self.d, covariance_matrix=np.eye(self.d))
            x_specific = np.repeat(x_specific, n, axis=0)

        f_star = self.f_star.get(x_specific)
        data_perturbation_specific = self.perturbation.get(x_specific)
        if self.local_perturbation is not None:
            rotation = self.local_perturbation.get(x_specific)
            data_perturbation_specific = np.einsum('njk,nk->nj', rotation, data_perturbation_specific)
        y_specific = f_star + data_perturbation_specific
        
        return x_specific, y_specific
    
    def generate_specific_y_given_x(self, x_specific, n=1):
        if n != 1:
            x_specifics = np.tile(x_specific[:, np.newaxis], (1, n))
        else:
            x_specifics = x_specific
        
        f_star = self.f_star.get(x_specifics)
        data_perturbation_specific = self.perturbation.get(x_specifics)
        if self.local_perturbation is not None:
            rotation = self.local_perturbation.get(x_specifics)
            data_perturbation_specific = np.einsum('njk,nk->nj', rotation, data_perturbation_specific)
        y_specific = f_star + data_perturbation_specific
        return x_specifics, y_specific
    
    def generate_y_given_x(self, x_samples):        
        f_star = self.f_star.get(x_samples)
        data_perturbation_specific = self.perturbation.get(x_samples)
        if self.local_perturbation is not None:
            rotation = self.local_perturbation.get(x_samples)
            data_perturbation_specific = np.einsum('njk,nk->nj', rotation, data_perturbation_specific)
        y_samples = f_star + data_perturbation_specific
        return y_samples

    def generate(self, n):
        if self.bias:
            x_train = get_perturbation(self.law_x, n, self.d-1, covariance_matrix=np.eye(self.d-1))
            x_train = np.hstack([np.ones((n, 1)), x_train])
        else:
            x_train = get_perturbation(self.law_x, n, self.d, covariance_matrix=np.eye(self.d))

        f_star = self.f_star.get(x_train)
        data_perturbation_train = self.perturbation.get(x_train)
        if self.local_perturbation is not None:
            rotation = self.local_perturbation.get(x_train)
            data_perturbation_train = np.einsum('njk,nk->nj', rotation, data_perturbation_train)
        y_train = f_star + data_perturbation_train
        
        return x_train, y_train
    
    def generate_train_calibration_test(self, n_train, n_calibration, n_test):
        x_train, y_train = self.generate(n_train)
        x_calibration, y_calibration = self.generate(n_calibration)
        x_test, y_test = self.generate(n_test)
        return x_train, y_train, x_calibration, y_calibration, x_test, y_test
    
    def generate_perturbation(self, n):
        data_perturbation_train = get_perturbation(self.noise_type, n, self.k, covariance_matrix=self.covariance_matrix)
        return data_perturbation_train
    
    def generate_perturbation_train_calibration_test(self, n_train, n_calibration, n_test):
        data_perturbation_train = self.generate_perturbation(n_train)
        data_perturbation_calibration = self.generate_perturbation(n_calibration)
        data_perturbation_test = self.generate_perturbation(n_test)
        return data_perturbation_train, data_perturbation_calibration, data_perturbation_test
    
def get_perturbation(perturbation, n_train, k, covariance_matrix=None):
    mean = np.zeros(k)
    if perturbation == "laplace":
        data_perturbation_train = np.random.laplace(0, 1, (n_train, k))
    elif perturbation == "gaussian":
        if covariance_matrix is None:
            raise ValueError("Covariance matrix must be provided for gaussian perturbation")
        data_perturbation_train = np.random.multivariate_normal(mean, covariance_matrix, n_train)
    elif perturbation == "uniform":
        data_perturbation_train = np.random.uniform(-1, 1, (n_train, k))
    elif perturbation == "pareto":
        data_perturbation_train = np.random.pareto(a=2.0, size=(n_train, k))  # a est le paramètre de forme
    elif perturbation == "lognormal":
        data_perturbation_train = np.random.lognormal(mean=0.0, sigma=1.0, size=(n_train, k))
    elif perturbation == "exponential":
        data_perturbation_train = np.random.exponential(scale=1.0, size=(n_train, k))
    elif perturbation == "chisquare":
        data_perturbation_train = np.random.chisquare(df=2, size=(n_train, k))  # df est le nombre de degrés de liberté
    elif perturbation == "poisson":
        data_perturbation_train = np.random.poisson(lam=3.0, size=(n_train, k))
    elif perturbation == "gamma":
        data_perturbation_train = np.random.gamma(shape=2.0, scale=1.0, size=(n_train, k))
    elif perturbation == "beta":
        data_perturbation_train = np.random.standard_t(df=3, size=(n_train, k))  # df est le nombre de degrés de liberté
    elif perturbation == "cauchy":
        data_perturbation_train = np.random.standard_cauchy(size=(n_train, k))
    else:
        data_perturbation_train = np.zeros((n_train, k))
    return data_perturbation_train
