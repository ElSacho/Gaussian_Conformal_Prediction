import os
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import QuantileTransformer
from sklearn.preprocessing import StandardScaler

def load_data(file_path):
    # Load data from a .npz file
    data = np.load(file_path)
    return data['X'], data['Y']


def split_and_preprocess(X, Y, splits=[0.7, 0.1, 0.1, 0.1], normalize=True, random_state=None, strategy="quantile"):
    """
    Splits the data according to the specified proportions and applies quantile normalization.

    Args:
        X (numpy.ndarray): The features.
        Y (numpy.ndarray): The labels.
        splits (list): List of data split percentages.
        random_state (int): Random seed for reproducibility.
        strategy (str): Normalization strategy, either "quantile" or "StandardScaler".

    Returns:
        dict: A dictionary containing the transformed datasets.
    """
    if not np.isclose(sum(splits), 1.0, atol=1e-10):
        raise ValueError("Proportions need to sum to 1.0.")
    
    n_samples = X.shape[0]
    split_sizes = [int(n_samples * p ) for p in splits]
    split_sizes[-1] = n_samples - sum(split_sizes[:-1])  
    
    if random_state is not None:
        np.random.seed(random_state)

    # Shuffle the data
    indices = np.random.permutation(n_samples)
    X, Y = X[indices], Y[indices]

    # Split the datasets according to the defined sizes
    start = 0
    subsets = {}
    subset_names = ["X_train", "X_stop", "X_calibration", "X_test"] if len(splits) == 4 else ["X_train", "X_calibration", "X_test"]
    
    for i, name in enumerate(subset_names):
        end = start + split_sizes[i]
        subsets[name] = X[start:end]
        subsets[name.replace("X_", "Y_")] = Y[start:end]
        start = end
    
    if not normalize:
        return subsets
    
    if strategy == "StandardScaler":
        # StandardScaler normalization
        print("StandardScaler")
        scaler = StandardScaler()
        subsets["X_train"] = scaler.fit_transform(subsets["X_train"])
        for name in subset_names[1:]:
            subsets[name] = scaler.transform(subsets[name])
        Y_scaler = StandardScaler()
        subsets["Y_train"] = Y_scaler.fit_transform(subsets["Y_train"])
        for name in [n.replace("X_", "Y_") for n in subset_names[1:]]:
            subsets[name] = Y_scaler.transform(subsets[name])
        return subsets
    
    # Quantile normalization for X
    x_transformer = QuantileTransformer(output_distribution='normal')
    subsets["X_train"] = x_transformer.fit_transform(subsets["X_train"])
    for name in subset_names[1:]:  # Ne pas refitter, appliquer la même transformation aux autres sets
        subsets[name] = x_transformer.transform(subsets[name])

    # Quantile normalization for Y
    y_transformer = QuantileTransformer(output_distribution='normal')
    subsets["Y_train"] = y_transformer.fit_transform(subsets["Y_train"])
    for name in [n.replace("X_", "Y_") for n in subset_names[1:]]:
        subsets[name] = y_transformer.transform(subsets[name])

    
    return subsets


