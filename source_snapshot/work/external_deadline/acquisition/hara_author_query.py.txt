import numba
import numpy as np

@numba.njit("float64[:](float64[:, :, :], float64[:, :], int64[:])", parallel=True)
def q_by_loss_diff_sub(loss_clfs, p_est, idx):
    K = len(loss_clfs)
    loss_diff = np.zeros(len(idx), dtype=np.float64)
    for k in numba.prange(len(idx)):
        v = idx[k]
        for i in range(K):
            for j in range(i+1, K):
                for c in range(p_est.shape[1]):
                    loss_diff[k] = loss_diff[k] + np.abs(loss_clfs[i, v, c] - loss_clfs[j, v, c]) * p_est[v, c]
    return loss_diff

def q_by_loss_diff(loss_clfs, p_est, idx, eps=1e-2, normalize=True):
    q = q_by_loss_diff_sub(loss_clfs, p_est, np.array(idx))
    if normalize:
        return (q + eps) / np.sum(q + eps)
    else:
        return q + eps

@numba.njit("float64[:](float64[:, :, :], float64[:, :], int64[:], float64[:])", parallel=True)
def q_by_loss_diff_squared_sub(loss_clfs, p_est, idx, D):
    K = len(loss_clfs)
    loss_diff = np.zeros(len(idx), dtype=np.float64)
    for k in numba.prange(len(idx)):
        v = idx[k]
        for i in range(K):
            for j in range(i+1, K):
                delta_D = D[i] - D[j]
                delta = 0.0
                for c in range(p_est.shape[1]):
                    delta_loss = loss_clfs[i, v, c] - loss_clfs[j, v, c]
                    delta = delta + p_est[v, c] * (delta_loss - delta_D)**2
                loss_diff[k] = loss_diff[k] + np.sqrt(delta)
    return loss_diff

def q_by_loss_diff_squared(loss_clfs, p_est, idx, eps=1e-2, normalize=True):
    D = np.array([np.mean(np.sum(p_est * loss_clfs[i], axis=1)) for i in range(loss_clfs.shape[0])])
    q = q_by_loss_diff_squared_sub(loss_clfs, p_est, np.array(idx), D)
    if normalize:
        return (q + eps) / np.sum(q + eps)
    else:
        return q + eps

def q_uniform(loss_clf, p_est, idx, normalize=True):
    if normalize:
        return np.full(len(idx), 1.0/len(idx))
    else:
        return np.full(len(idx), 1.0)

@numba.njit("int64(float64[:], int64)")
def sample_from_p(p, seed):
    np.random.seed(seed)
    while True:
        j = np.random.choice(p.size, 10000)
        t = np.random.rand(j.size)
        k = np.where(t < p[j])[0]
        if k.size == 0:
            continue
        else:
            j = j[k[0]]
            break
    return j