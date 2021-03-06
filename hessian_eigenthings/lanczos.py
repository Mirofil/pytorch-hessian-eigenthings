""" Use scipy/ARPACK implicitly restarted lanczos to find top k eigenthings """
import numpy as np
import torch
from scipy.sparse.linalg import LinearOperator as ScipyLinearOperator
from scipy.sparse.linalg import eigsh
from warnings import warn

import hessian_eigenthings.utils as utils


def lanczos(
    operator,
    num_eigenthings=10,
    which="LM",
    max_steps=20,
    tol=1e-6,
    num_lanczos_vectors=None,
    init_vec=None,
    use_gpu=False,
    fp16=False,
):
    """
    Use the scipy.sparse.linalg.eigsh hook to the ARPACK lanczos algorithm
    to find the top k eigenvalues/eigenvectors.

    Parameters
    -------------
    operator: power_iter.Operator
        linear operator to solve.
    num_eigenthings : int
        number of eigenvalue/eigenvector pairs to compute
    which : str ['LM', SM', 'LA', SA']
        L,S = largest, smallest. M, A = in magnitude, algebriac
        SM = smallest in magnitude. LA = largest algebraic.
    max_steps : int
        maximum number of arnoldi updates
    tol : float
        relative accuracy of eigenvalues / stopping criterion
    num_lanczos_vectors : int
        number of lanczos vectors to compute. if None, > 2*num_eigenthings
    init_vec: [torch.Tensor, torch.cuda.Tensor]
        if None, use random tensor. this is the init vec for arnoldi updates.
    use_gpu: bool
        if true, use cuda tensors.
    fp16: bool
        if true, keep operator input/output in fp16 instead of fp32.

    Returns
    ----------------
    eigenvalues : np.ndarray
        array containing `num_eigenthings` eigenvalues of the operator
    eigenvectors : np.ndarray
        array containing `num_eigenthings` eigenvectors of the operator
    """
    if isinstance(operator.size, int):
        size = operator.size
    else:
        size = operator.size[0]
    shape = (size, size)

    if num_lanczos_vectors is None:
        num_lanczos_vectors = min(2 * num_eigenthings, size - 1)
    if num_lanczos_vectors < 2 * num_eigenthings:
        warn(
            "[lanczos] number of lanczos vectors should usually be > 2*num_eigenthings"
        )

    def _scipy_apply(x):
        x = torch.from_numpy(x)
        x = utils.maybe_fp16(x, fp16)
        if use_gpu:
            x = x.cuda()
        out = operator.apply(x)
        out = utils.maybe_fp16(out, fp16)
        out = out.cpu().numpy()
        return out

    scipy_op = ScipyLinearOperator(shape, _scipy_apply)
    if init_vec is None:
        init_vec = np.random.rand(size)
    elif isinstance(init_vec, torch.Tensor):
        init_vec = init_vec.cpu().numpy()

    init_vec = utils.maybe_fp16(init_vec, fp16)
    eigenvals, eigenvecs = eigsh(
        A=scipy_op,
        k=num_eigenthings,
        which=which,
        maxiter=max_steps,
        tol=tol,
        ncv=num_lanczos_vectors,
        return_eigenvectors=True,
    )
    return eigenvals, eigenvecs.T
