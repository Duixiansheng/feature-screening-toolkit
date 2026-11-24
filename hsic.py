"""HSIC Gram products with the unchanged Step 5 Gaussian lookup and Delta kernel."""
import numpy as np

def kernel_terms(x, y, lookup=True, tile=256):
    n, d = x.shape
    span_raw = np.ptp(x, axis=0)
    span = np.maximum(span_raw, 1e-12)
    lut = np.exp(-.5 * (span[:, None] * np.linspace(0, 1, 4096))**2)
    counts = np.bincount(y, minlength=2)
    row_sums = np.zeros((n, d+1))
    products = np.zeros((d+1, d+1))
    for i in range(0,n,tile):
        a = slice(i,min(i+tile,n))
        for j in range(i,n,tile):
            b = slice(j,min(j+tile,n))
            difference = abs(x[a,None,:] - x[None,b,:])
            if lookup:
                idx = np.rint(difference * (4095/span)).astype(np.int32).clip(0,4095)
                values = lut[np.arange(d), idx]
            else:
                values = np.exp(-.5 * difference**2)
            label = (y[a,None] == y[None,b]) / counts[y[None,b]]
            kernel = np.concatenate((values, label[...,None]), axis=2)
            row_sums[a] += kernel.sum(axis=1)
            if i != j:
                row_sums[b] += kernel.sum(axis=0)
            flat = kernel.reshape(-1,d+1)
            products += (flat.T @ flat) * (1 if i == j else 2)
    # Center the Frobenius products algebraically using only the row sums.
    sums = row_sums.sum(0)
    products -= (2/n) * (row_sums.T @ row_sums)
    products += np.outer(sums,sums)/(n*n)
    constant = np.r_[span_raw == 0, len(np.unique(y))<2]
    products[constant,:] = products[:,constant] = 0
    norm = np.sqrt(np.maximum(products.diagonal(),1e-30))
    products /= norm[:,None]*norm
    return products[:-1,:-1],products[:-1,-1]
