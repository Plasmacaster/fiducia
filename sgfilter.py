# -*- coding: utf-8 -*-
"""
Created on Wed Sep  1 16:18:11 2021

Contains functions for using Gram Polynomial based Savitzky-Golay filters that
self-optimize using MMSE cost functions.

Based upon the work that can be found in these two papers:
    Peter A. Gorry "General Least-Squares Smoothing and Differentiation by the
    Convolution (Savitzky-Golay) Method" Anal. Chem. 1990, 62, 570-573
    
    Mohammad Sadeghi, Fereidoon Behnia "Optimum window length of
    Savitzky-Golay filters with arbitrary order" arxiv 1808.10489


@author: Daniel Barnak
"""

import numpy as np
import pandas as pd
import math
from scipy.signal import savgol_filter
from scipy.special import factorial

import scipy as sp

def gen_fact(a, b, method = 'vector'):    
    """
    Generalized factorial between two numbers a and b. See Gorry paper for
    further details and definition. Essentially a! truncated by b, i.e.
    a*(a-1)*(a-2)*...*(a-b+2)*(a-b+1). If b = 0, returns 1.

    Parameters
    ----------
    a : int
        Right bound number.
    b : int
        Left bound number.
    method : str
        Chooses between using single values or lists of values for inputs a and
        b. The 'old' method should probably be done away with. The default is
        'vector'.

    Returns
    -------
    gf : integer
        output factorial in the range of a-b to a.

    """
    # unparallel gen_fact routine
    if method == 'old':
        gf = 1
        for idx in range(a-b, a):
            gf = gf*(idx+1)
        return gf
    
    #vectorized factorial based on scipy functions
    if method == 'vector':
        spFact = sp.special.factorial
        fact = sp.vectorize(spFact, otypes='O')
        diff = a - b
        diffBool = (a-b>=0)*1
        num = fact(a, exact=True)
        denom = fact(np.abs(diff), exact=True)
        gf = np.clip(num/denom*diffBool, 0, None)
        return gf

# the Gram Polynomial 
def gram_poly(i, m, k, s, method = 'vector'):
    """
     Iterative definition of Gram polynomials and their derivatives
    
     Parameters
     ----------
     i : integer
         Evaluation point of the Gram polynomial.
     m : integer
         Window parameter for the Savitzky-Golay filter. The window width is
         given by 2*m + 1, since the window for the filter must be odd.
     k : integer
         Order of the Gram polynomimal.
     s : integer
         Derivative order for the Gram polynomial. Typically set to 0 in use
         for all Savitzky-Golay filtering.
    method : str
        Choose the calculation method of the Gram polynomial. The default is
        'vector' and the default gives the fastest results.
    
     Returns
     -------
     gramPoly : real
         Returns function value of the Gram polynomial at point i.
    
    """
    if method == 'new':
        if k == 0:
            gram_poly = 1
            return gram_poly
        else:
            jArr = np.arange(0, k + 1)
            terms = np.zeros(k + 1)
            for idx, j in enumerate(jArr):
                jFact = factorial(j)
                gf1 = gen_fact(j + k, 2*j, method = 'old')
                gf2 = gen_fact(m + i, j, method = 'old')
                gf3 = gen_fact(2*m, j, method = 'old')
                gfProd = gf1*gf2/gf3
                terms[idx] = ((-1)**(j + k))/(jFact**2)*gfProd
            gram_poly = np.sum(terms)
            return gram_poly
        
    if method == 'vector':
        if k == 0:
            gram_poly = 1
            return gram_poly
        else:
            jArr = np.arange(0, k + 1)
            terms = np.zeros((k + 1, len(i)))
            for idx, j in enumerate(jArr):
                jFact = factorial(j)
                gf1 = gen_fact(j + k, 2*j)
                gf2 = gen_fact(m + i, j)
                gf3 = gen_fact(2*m, j)
                gfProd = gf1*gf2/gf3
                terms[idx] = ((-1)**(j + k))/(jFact**2)*gfProd
        gram_poly = np.sum(terms, axis = 0)
        return gram_poly
    
    if method == 'old':
        if k > 0:
            term1 = (4*k-2)/(k*(2*m - k + 1))
            term2 = ((k-1)*(2*m + k)/(k*(2*m - k + 1)))
            gram1 = (i*gram_poly(i, m, k-1, s) + s*gram_poly(i, m, k-1, s-1))
            gram_poly = term1 * gram1 - term2 * gram_poly(i, m, k-2, s)
            return  gram_poly
        elif (k == 0 and s == 0):
            gram_poly = 1.0
            return gram_poly
        else:
            gram_poly = 0.0
            return gram_poly
    return gram_poly
    
# convolution weights for quadratic smoothing
def conv_weight(i, t, m, n, s = 0, method = 'vector'):
    """
    Generates weight tables that solve the smoothing coefficients for the
    Gram polynomials. Called only once to calculate smoothing

    Parameters
    ----------
    i : integer
        Refers to the index of points that are sent through the Savitzky-Golay
        filter. 
    t : integer
        Refers to the index of the polynomial fit from the Savitzky-Golay. For
        a window of 2*m + 1 points, the ith point is the actual data, and the
        tth point is the point of the polynomial fit over the entire window.
    m : integer
        Window parameter for the Savitzky-Golay filter. The window width is
        given by 2*m + 1, since the window for the filter must be odd.
    n : integer
        The order of the polynomials used in the filter
    s : integer, optional
        Derivative order for the Gram polynomial. Typically set to 0 in use
        for all Savitzky-Golay filtering.
    method : str, optional
        Choose the calculation method of the weights. The default is
        'vector' and the default gives the fastest results.

    Returns
    -------
    weightSum : ndarray
        An array of values that give a polynomial fit across 2*m + 1 points
        that minimizes the cost function for the fit.

    """
    k = np.arange(0, n)
    weightSum = 0
    for k in range(0, n+1):
        coeff1 = (2*k+1)*gen_fact(2*m, k)/gen_fact(2*m+k+1, k+1)
        gram1 = gram_poly(i,m,k,0, method = method)
        gram2 = gram_poly(t,m,k,s, method = method)
        if method == 'vector':
            weightSum = weightSum + (coeff1 * np.outer(gram1, gram2))
        if method == 'new':
            weightSum = weightSum + (coeff1 * gram1 * gram2)
    return weightSum

def sg_filter_gram(signal, window, order, der = 0, method = 'vector'):
    """
    Filters the input signal using the Savitzky-Golay algorithm with Gram
    polynomial basis functions.
    
    Parameters
    ----------
    signal : ndarray
        User input signal to be filtered.
    window : integer
        Window parameter m for the Savitzky-Golay filter. The window width is
        given by 2*m + 1, since the window for the filter must be odd.
    order : integer
        The order of the polynomials used in the filter
    der : integer, optional
        Derivative order for the Gram polynomial. Typically set to 0 in use
        for all Savitzky-Golay filtering. The default is 0.
    method : string, optional
        DESCRIPTION. The default is 'vector' and the defaul gives the fastest
        result.

    Returns
    -------
    sgFilter : ndarray
        The resulting filtered signal.

    """
    signalLen = len(signal)
    m =  window
    n = order
    s = der
    
    if method == 'new':
        weightArr = np.zeros((2*m+1, 2*m+1))
        for i in range(-m, m+1):
            for t in range(-m, m+1):
                weightArr[i + m, t + m] = 1*conv_weight(i,t,m,n,s, 
                                                        method = method)
    if method == 'vector':
        i = np.arange(-m, m+1)
        t = np.arange(-m, m+1)
        weightArr = 1*conv_weight(i,t,m,n,s, method = method )
    

    sgFilter = pd.Series(0., index = np.arange(signalLen))
    for idx in range(m+1, signalLen-1):
        if idx <= m+1:
            signalSeg = np.asarray(signal[0:2*m + 1])
            filterArr = weightArr * signalSeg
            filterSeg = np.sum(filterArr, axis=1)
            firstSeg = filterSeg[0:m+2]
            # sgFilter[0:m] = filterSeg[0:m]
            # break
        elif idx + m >= signalLen:
            rightIdx = (2*m + 1)
            signalSeg = np.asarray(signal[signalLen - rightIdx:signalLen])
            filterArr = weightArr * signalSeg
            filterSeg = np.sum(filterArr, axis=1)
            lastSeg = filterSeg[m+1:2*m+1]
            break
            # sgFilter = filterSeg[signalLen-m:signalLen]
        else:
            rightIdx = (idx + 2*m + 1)
            signalSeg = np.asarray(signal[idx - m:idx + m + 1])
            ### old method ###
            # filterArr = weightArr * signalSeg
            # filterSeg = np.sum(filterArr, axis = 1)
            # filterPoint = filterSeg[m+1]
            ### old method ###
            ### new method ### # credit to V. Gopalaswamy
            filterArr = weightArr[:, m+1] * signalSeg
            filterPoint = np.sum(filterArr)
            sgFilter[idx] = filterPoint
            ### new method ###
        
    # append first and last segments to the sg filter array
    sgFilter[0:m+2] = firstSeg
    sgFilter[signalLen-(m):signalLen] = lastSeg
    
    return sgFilter

def noise(signal):
    """
    Automatic calculation of the noise present in the input signal. Uses a
    default coarse and fine Savitzky-Golay filter to determine the correct
    sigma of the noise distribution. Users are encouraged to use this function
    as little as possible and to instead rely on physical calculations of
    their expected noise levels on the input signals.

    Parameters
    ----------
    signal : ndarray
        User input signal to be filtered.

    Returns
    -------
    sigma : real
        The standard deviation of the random noise in the signal. Used in the
        calculation for optimal window length of the filter.

    """
    sgFilter = savgol_filter(signal, 101, 3)
    noise1 = signal-sgFilter
    noise1SG = savgol_filter(noise1, 31, 3)
    noise2 = noise1-noise1SG
    # noise1Var = np.var(noise1)
    sigma = np.var(noise2)
    # noiseMean = np.mean(noise2)
    # noiseMin = np.min(noise1)
    # noiseMax = np.max(noise2)
    # points = np.linspace(noiseMin, noiseMax, 5000)
    # sgMaster = (signal - noise2)
    return sigma

def n_opt(signal, der = 0, sigma = "auto", method = 'vector', print_n = False):
    """
    Calculates the optimal window length using a slightly modified version of
    the algorithm outlined in Sadeghi et al.

    Parameters
    ----------
    signal : ndarray
        User input signal to be filtered.
    der : integer, optional
        Derivative order of the Savitzky-Golay filter. Use this to calculate
        the filtered derivative of the input signal. The default is 0.
    sigma : real, optional
        The standard deviation of noise associated with the input signal.The 
        default is "auto", which calls the noise function to estimate this
        value.
    method : string, optional
        Which method, either vectorized ('vector') or serialized ('new'), to 
        use when finding the optimum window n. The default is 'vector' and the
        default gives the fastest result.
    print_n : string, optional
        Prints the window size for each iteration of the optimization. The
        default is 'False'

    Returns
    -------
    n1 : integer
        The optimal window length for the filtering the input signal. Use this
        window length for the input m for the sg_filter_gram function.

    """
    nOpt = 3
    n1 = 1
    if (sigma == "auto"):
        sigma = noise(signal)
    while np.abs(nOpt-n1) > 1:
        k = 2
        if print_n == True:
            print('n1 = ' +str(int(2*np.floor(nOpt/2) + 1)))
        n1 = int(2*np.floor(nOpt/2) + 1)
        y = sg_filter_gram(signal, n1, k, der, method = method)
        yPrime = np.diff(y)
        dy = sg_filter_gram(yPrime, n1, k, der, method = method)
        d2y = np.diff(sg_filter_gram(dy, n1, k, der, method = method))
        d3y = np.diff(sg_filter_gram(d2y, n1, k, der, method = method))
        c1 = np.mean(d3y**2)
        num = 2*(k + 2)*(np.math.factorial(2*k + 3))**2
        denom = (np.math.factorial(k + 1))**2
        root = (2*k + 5)
        nOpt = ((num/denom)*(sigma/c1))**(1/root)
    return int(n1)