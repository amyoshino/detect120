from __future__ import print_function
##CUSP UO 2016
__author__ = "fbb"

import glob
import numpy as np
import optparse
import sys
import os
import pickle as pkl
import json
import scipy.optimize
import datetime
import itertools
import matplotlib
matplotlib.use('agg')
import pylab as pl
import subprocess

from images2gif import writeGif
from PIL import Image, ImageSequence
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
import IPython.display as IPdisplay
import multiprocessing as mpc

from findImageSize import findsize
s = json.load( open("fbb_matplotlibrc.json") )
pl.rcParams.update(s)

### EXTRACT: if True extracts the lightcurves from imaging data
EXTRACT = True
EXTRACT = False
NOPARALLEL = True
NOPARALLEL = False
PCAonly = True
#PCAonly = False
### READ: if True reads the results of the PCA/KM clustering
### stored in earlier runs, if they exist
READ = True
READ = False
DETREND = 0
### nmax: maximum number of datapoints per lightcurve (overwritten by 
#nmax=100
### lmax: maximum number of windows to use 
#lmax = 10


font = {'size'   : 13}

kelly_colors_hex = [
    '#FFB300', # Vivid Yellow
    '#803E75', # Strong Purple
    '#FF6800', # Vivid Orange
    '#A6BDD7', # Very Light Blue
    '#C10020', # Vivid Red
    '#CEA262', # Grayish Yellow
    '#817066', # Medium Gray
    '#007D34', # Vivid Green
    '#F6768E', # Strong Purplish Pink
    '#00538A', # Strong Blue
    '#FF7A5C', # Strong Yellowish Pink
    '#53377A', # Strong Violet
    '#FF8E00', # Vivid Orange Yellow
    '#B32851', # Strong Purplish Red
    '#F4C800', # Vivid Greenish Yellow
    '#7F180D', # Strong Reddish Brown
    '#93AA00', # Vivid Yellowish Green
    '#593315', # Deep Yellowish Brown
    '#F13A13', # Vivid Reddish Orange
    '#232C16', # Dark Olive Green
    ]

wave = lambda t, phi, fq: np.sin(2.*fq*np.pi*t + phi*np.pi)/0.7
resd = lambda phi, fq, x, t: np.sum((wave(t*fq, phi, fq) - x)**2)
resd_freq = lambda fq, phi, x, t: np.sum((wave(t*fq, phi, fq) - x)**2)

def rsquared (data,model):
    datamean = data.mean()
    return np.sum((model - datamean)**2)/np.sum((data-datamean)**2)

def chisq(data, model):
    return np.sum((data-model)**2)/(data-model).std()/(len(data)-2)

def makeGifLcPlot(x, y, ind, ts, aperture, fnameroot,
                  imshape, flist, showme=False, fft=False,
                  stack=None, outdir="./"):

    fig = callplotw(x, y, ind, ts, flist, aperture,
                    imshape, fname = fnameroot,
                    giflen=160, stack=stack, outdir=outdir)

    if not fft: fig.savefig(fnameroot + "_%d_%d"%(x,y)+".png")
    else: fig.savefig(fnameroot + "_%d_%d"%(x,y)+"_fft.png")
    if showme:
        pl.show()
        print (fnameroot + "_%d_%d"%(x,y)+".GIF")
        IPdisplay.Image(url=fnameroot + "_%04d_%04d"%(x,y)+".GIF")
    pl.close(fig)
    
def callplotw(xc, yc, i, ts, flist, aperture, imshape, fft=False,
              fname = None, giflen=40, stack=None, outdir='./'):

   fig = pl.figure(figsize=(10,10))
   ax1 = fig.add_subplot(221)
   if stack is None:
       print ("no stack")
       ind = min([len(flist),10])
       img = np.fromfile(flist[ind],
                        dtype=np.uint8).reshape(imshape['nrows'],
                                                imshape['ncols'],
                                                imshape['nbands'])
   else:
       img = stack

   plotwindows(xc-25, yc-25, xc+25, yc+25,
               img, imshape, axs=ax1, c='w',
               plotimg = 0)
   ax1.set_title("window coordinates: %d %d"%(xc, yc))
    
   ax2 = fig.add_subplot(222)
   
   plotwindows(xc-aperture, yc-aperture, xc+aperture, yc+aperture, 
               img, imshape, wsize=(30,30), axs=ax2, c='Lime',
               plotimg = 0)
   ax2.set_title("aperture %d, index %d"%(aperture, i))
   ax2.axis('off')
   
   if fname:
       try:
           images = [Image.fromarray(np.fromfile(f,
                             dtype=np.uint8).reshape(imshape['nrows'],
                                                     imshape['ncols'],
                                imshape['nbands'])[yc-22:yc+21,
                                                   xc-22:xc+21]) \
                 for f in flist[:giflen]]
           fullfname = outdir + "/gifs/" + fname.split('/')[-1]
           try: 
               writeGif(fullfname + "_%04d_%04d"%(xc,yc)+".GIF",
                        images, duration=0.01)
           except: 
               print ("failed to write to disk")
               pass
       #print ("Done writing GIF %s_%04d_%04d.GIF"%(fname, xc, yc))
       except ValueError:
           print ("Error in giffing") 

   ax3 = fig.add_subplot(223)
   ax3.plot(ts, label = "time series")
   ax3.legend()
   ax4 = fig.add_subplot(224)
   if fft:
       ax4.plot(np.abs(np.fft.irfft(ts)), 
                label = "ifft")
       #ax4.plot([0.25, 0.25], [ax4.get_ylim()[0], ax4.get_ylim()[1]])
   else:
       ax4.plot(np.abs(np.fft.rfft(ts))[2:], 
                label = "fft")
       ax4.plot([0.25, 0.25], [ax4.get_ylim()[0], ax4.get_ylim()[1]])
   ax4.legend()
   return fig


def sparklines(data, lab, ax, x=None, title=None,
               color='k', alpha=0.3,
               twomax = True, maxminloc=False, nolabel=False):
    if x is None :#and len(x)==0:
        x=np.arange(data.size)
    xmax, xmin = -99, -99
    ax.plot(x, data, color=color, alpha=alpha)
    ax.axis('off')
    ax.set_xlim(-(x.max()-x.min())*0.1, (x.max()-x.min())*1.1)
    ax.set_ylim(ax.get_ylim()[0]-(ax.get_ylim()[1]-ax.get_ylim()[0])/10, ax.get_ylim()[1])

    ax.text(-0.1, 0.97, lab, fontsize = 10, 
            transform = ax.transAxes)
    if title:
        ax.plot((0,ax.get_xlim()[1]), 
                (ax.get_ylim()[1], ax.get_ylim()[1]), 'k-',)

    if nolabel:
       return  ((np.nan, np.nan), np.nan)
    ymax = max(data[:-5])
    xmaxind = np.where(data[:-5] == ymax)[0]
    #print (xmaxind, x[xmaxind])
    try:
        xmax =  x[xmaxind]
#        print ("xmax", xmax)
        ax.plot(xmax, ymax, 'o', ms=5, color='SteelBlue')
        if twomax:
            if xmaxind-3>0:
                max2data = np.concatenate([data[:xmaxind-3],data[xmaxind+3:-5]])
                x2 = np.concatenate([x[:xmaxind-3],x[xmaxind+3:-5]])
            else:
                max2data = data[3:-5]
                x2 = x[3:-5]
            xmax1 =  x2[np.where(max2data == max(max2data))[0]]
            #        print ("xmax1", xmax1, max(max2data))
            ax.plot(xmax1, max(max2data), 'o', ms=5,
                    color='SteelBlue', alpha=0.5)
        else: xmax1=np.nan  
    except ValueError:
        try:
            xmax = x[xmaxind[0]]
            ax.plot(xmax, ymax, 'o', ms=5, color='SteelBlue')

            max2data = np.concatenate([data[:xmax-5],data[xmax+5:-5]])
            x2 = np.concatenate([x[:xmax-5],x[xmax+5:-5]])
            xmax1 =  x2[np.where(max2data == max(max2data))[0][0]]
            ax.plot(xmax1, max(max2data), 'o', ms=5,
                color='SteelBlue', alpha=0.5)
        except IndexError:
            xmax, xmax1 = np.nan, np.nan
    try:
        xmin =  x[2:-5][np.where(data[2:-5] == min(data[2:-5]))[0]]   
        ax.plot(xmin, min(data[2:-5]), 'o', ms=5, color='IndianRed')
    except ValueError:
        try:
            xmin =  x[2:-5][np.where(data[2:-5] == min(data[2:-5]))[0][0]]  
            ax.plot(xmin, min(data[2:-5]), 'o', ms=5, color='IndianRed')
            
        except IndexError: pass
        
    if not isinstance(xmax, (np.int64,float)) and len(xmax)==0: xmax=np.nan
    if not isinstance(xmax1, (np.int64,float)) and len(xmax1)==0: xmax1=np.nan
    if not isinstance(xmin, (np.int64,float)) and len(xmin)==0: xmin=np.nan    
    
    if maxminloc:
        ax.text(1, 0.4, "%.2f"%(xmin), fontsize = 10, 
                transform = ax.transAxes, ha = 'right', color='IndianRed')
        ax.text(1, 0.7, "%.2f"%(xmax), fontsize = 10, 
                transform = ax.transAxes, ha = 'right', color='SteelBlue')
    else:
        ax.text(1, 0.4, "%.1f"%(min(data)), fontsize = 10, 
                transform = ax.transAxes, ha = 'right', color='IndianRed')
        ax.text(1, 0.7, "%.1f"%(max(data)), fontsize = 10, 
                transform = ax.transAxes, ha = 'right', color='SteelBlue')  

    return ((xmax, xmax1), xmin)


def extraction(((coord), xfreq, lmax,
               flist, filepattern, imsize, outdir,
                options, fig, ax, figfft, axfft)):

    cc,i = coord
    bs, fs  = get_plot_lca ((int(cc[0]+0.5)-options.aperture,
                             int(cc[1]+0.5)-options.aperture, 
                             int(cc[0]+0.5)+options.aperture+1,
                             int(cc[1]+0.5)+options.aperture+1),
                            flist, 
                            filepattern+'_x%d_y%d_ap%d'%(int(cc[0]+0.5),
                                                         int(cc[1]+0.5), 
                                                         options.aperture),
                            imsize, fft=options.fft,
                            verbose=False, showme=options.showme,
                            outdir = outdir)

    #pl.plot(b1)
    #print (bs[i].size)
    
    #sparklines(bs, '%d %d:%d'%(i, int(cc[0]), int(cc[1])), ax[-1])
    #if options.fft:
        #axfft.append(figfft.add_subplot(lmax/2+1,2,i+1))                
        #sparklines(fs[2:-5], '%d %d:%d'%(i, int(cc[0]), int(cc[1])),
        #           axfft[-1], x=xfreq[2:-5],
        #           maxminloc=options.fft)
        
    return bs, fs

def get_plot_lca (coords, flist, fname, imshape, fft=False, c='w', verbose=True,
                   showme=False, outdir='./'):
    
    if not fft:
        a = read_to_lc(coords, flist, fname, imshape, fft=fft,
                       showme=showme, c=c, verbose=verbose, outdir=outdir)
        afft = np.ones(a.size/2+1) * np.nan

    else:
        afft, a = read_to_lc(coords, flist, fname, imshape, fft=fft,
                  showme=showme, c=c, verbose=verbose, outdir=outdir)
    #print (a)
    flux0=(a-np.nanmean(a))/np.nanstd(a)
    flux=flux0.copy()
    
    if showme:
        pl.rc('font', **font)

        fig = pl.figure(figsize=(15,5))
        pl.plot(flux, color=c)
        pl.xlabel("img number")
        pl.ylabel("standardized flux")
        pl.show()
        pl.close(fig)
    return flux0, afft


def read_to_lc(coords, flist, fname, imshape, fft=False, c='w',
               showme=False, verbose = False, outdir = './'):
    x1, y1, x2, y2 = coords
    fullfname = outdir + "/pickles/" + fname.split('/')[-1]
    nmax = len(flist)
    if showme :
        plotwindows(x1,y1,x2,y2, flist[0], c=c)
    rereadnow = EXTRACT

    if not rereadnow:
        try:
            if verbose : print (fullfname+".pkl", os.isfile(fullfname+".pkl"))
            if not fft:
                try:
                    a = pkl.load(open(fullfname+".pkl",'rb'))
                except ValueError:
                    rereadnow = True
            else:
                try:
                    a = pkl.load(open(fullfname+".pkl",'rb'))
                    #print ("printing now ",a.size)
                    #pl.plot(a)
                    #pl.show()
                    afft = pkl.load(open(fullfname+"_fft.pkl",'rb'))
                    afft[0] = min(a)
                except ValueError:
                    rereadnow = True                    
        except:
            rereadnow = True
            print ("missing files: changing reread to True")
        
    if rereadnow:
        a = np.ones(nmax)*np.nan
        for i,f in enumerate(flist):
            try:
                a[i] = np.fromfile(f,
                        dtype=np.uint8).reshape(imshape['nrows'],
                                                imshape['ncols'],
                                imshape['nbands'])[y1:y2,x1:x2].sum()
            except: 
                a[i]=float('NaN')
                continue
        if not fft:
            pkl.dump(a, open(fullfname+".pkl","wb"))
        else:
            afft = np.abs(np.fft.rfft(a))
            pkl.dump(afft,open(fullfname+"_fft.pkl","wb"))
            if not os.path.isfile(fullfname+"_fft.pkl"):
                pkl.dump(a, open(fullfname+".pkl","wb"))
            
    try:
        f0 = np.fromfile(flist[0],
                     dtype=np.uint8).reshape(imshape['nrows'],
                                             imshape['ncols'],
                                     imshape['nbands'])[y1:y2,x1:x2]
    except IndexError:
        print ("something is wrong with the file list ", flist)
    '''
    print (flist[0])
    print (np.fromfile(flist[0],
                       dtype=np.uint8).reshape(imshape['nrows'],
                                               imshape['ncols'],
                                               imshape['nbands']))
    print (np.fromfile(flist[0],
                      dtype=np.uint8).reshape(imshape['nrows'],
                                              imshape['ncols'],
                                              imshape['nbands'])[y1:y2,x1:x2])
        
        #print (glob.glob(impath+"*.raw"))
    '''
    area = (x2-x1)*(y2-y1)
    if verbose:
        print ('mean: {0:.2f}, stdev: {1:.2f}, area: {2:d} pixels, {3:d} images, average flux/pixel: {4:.1f}'.format(
                    np.nanmean(a), np.nanstd(a), area,
            a.size, np.nanmean(a)/float(area)))


    if verbose:
        R = float(f0[:,:,0].sum())
        G = float(f0[:,:,1].sum())
        B = float(f0[:,:,2].sum())
        mx = np.argmax([R,G,B])
        colors= ['Red','Yellow','Blue']
        print (colors[mx],
               ': R: {0:.2f} G: {1:.2f} B: {2:.2f}'.format(1, G/R, B/R))

    if not fft: return  a
    
    return afft, a



def plotwindows(x1,y1,x2,y2, img, imshape, wsize=None,
                axs=None, c='w', plotimg=0):

    if not axs :
        fig, axs = pl.subplots(1,1,figsize=(15,15))
    #pl.imshow(np.fromfile(flist[0],dtype=np.uint8)\.reshape(nrow,ncol,nband))
    #pl.imshow(np.fromfile(flist[0],dtype=np.uint8).reshape(nrow,ncol,nband)[x1:x2,y1:y2])
    #axs.imshow(np.fromfile(flist[0],dtype=np.uint8).reshape(nrow,ncol,nband)[y1:y2,x1:x2],  interpolation='nearest')

    xmin,xmax,ymin,ymax = 0,0,0,0
    if plotimg == 0:
        if wsize:
            xmin = int(max(0,(x1+x2)/2-wsize[0]))
            xmax = int(min(imshape['ncols'],(x1+x2)/2+wsize[0]))
            ymin = int(max(0,(y1+y2)/2-wsize[1]))
            ymax = int(min(imshape['nrows'],(y1+y2)/2+wsize[1]))
            #print (ymin, ymax, xmin, xmax)
            axs.imshow(img[ymin:ymax, xmin:xmax],
                       interpolation='nearest')
        else:
            axs.imshow(img,
                       interpolation='nearest')            
        axs.set_xlim(0, axs.get_xlim()[1])
        axs.set_ylim(axs.get_ylim()[0], 0)
        
    axs.plot([x1-xmin,x2-xmin],[y1-ymin,y1-ymin], '-', color='%s'%c)    
    axs.plot([x2-xmin,x2-xmin],[y1-ymin,y2-ymin], '-', color='%s'%c)    
    axs.plot([x1-xmin,x2-xmin],[y2-ymin,y2-ymin], '-', color='%s'%c)    
    axs.plot([x1-xmin,x1-xmin],[y2-ymin,y1-ymin], '-', color='%s'%c)    
    #pl.show()

def fit_freq(freq, ts):
    lts =  np.arange(ts.size)
    savephi = 0
    minres = 99e9
    for phi in np.arange(0,1.1,0.1)*2*np.pi:
        #print (phi)
        res = resd(phi, np.abs(freq), ts, lts)
        #print (res, minres)
        if res<minres:
            savephi = phi
            minres = res
        #print (savephi)
            
    phi0 = savephi   
    pl.figure()
    pl.plot(ts)
    pl.plot(lts,wave(lts*freq,
                    phi0, np.abs(freq)))
    #pl.show()
    fits = scipy.optimize.minimize(resd, phi0, args=(np.abs(freq),
                                                     ts, lts))            

    phase = fits.x%2
    sinwave = wave(lts*freq,
                    phase, np.abs(freq))

    if len(sinwave) == 2: thiswave = sinwave[0]
    chi2 = chisq(ts, sinwave)

    return phase, chi2, sinwave

    


def fit_waves(filepattern, lmax, nmax, timeseries, transformed, km,
              goodkmeanlabels, ntot, img, fnameroot,
              km_freqs, stack, bs, logfile, allights,
              aperture, imsize, flist, xfreq, chi2thr,
              fft=False,   showme=False,
              outdir="./", outdir0="./"):

    newntot = 0
    j = 0
    fig = pl.figure(figsize=(10,(int(ntot/2)+1)))#figsize=(10,100))
    ax = []
    fig2 = pl.figure()

    axs0 = fig2.add_subplot(211)
    axs1 = fig2.add_subplot(212)    
    #fig2 = pl.figure()
    #axs2 = fig2.add_subplot(111)
    
    axs0.imshow(stack, interpolation='nearest')
    axs0.set_xlim(0, axs0.get_xlim()[1])
    axs0.set_ylim(axs0.get_ylim()[0], 0)
    axs0.axis('off')

    axs1.imshow(img,  interpolation='nearest')
    axs1.set_xlim(0, axs1.get_xlim()[1])
    axs1.set_ylim(axs1.get_ylim()[0], 0)
    axs1.axis('off')
    print ("")
    
    ###start here if you just want to do the fitting

    #for i,cc in enumerate(allights[:lmax]):
    phases = np.zeros((6,len(bs)))*float('NaN')
    try:
        freq = [km_freqs[goodkmeanlabels[0]], km_freqs[goodkmeanlabels[1]]]
        i=2
        freq[0] = [ 0.25]
        while (freq[0] == freq[1] and i<len(goodkmeanlabels)):
            #print (goodkmeanlabels)
            freq[1] = km_freqs[goodkmeanlabels[i]]
            i=i+1
        if freq[0] == freq[1]: freq[1] = [0.32]
    except IndexError:
        freq = (km_freqs[goodkmeanlabels[0]])
        

    
    if fft:
        outphasesfile = open(filepattern+"_fft_phases_N%04dW%04dS%04d.dat"%(nmax,lmax, options.skipfiles), "w")
    else:
        outphasesfile = open(filepattern+"_phases_N%04dW%04dS%04d.dat"%(nmax,lmax,
         options.skipfiles), "w")
        
    print ("#index,x,y,freq,phase", file=outphasesfile)
    figsp = pl.figure(figsize = (10,(int(lmax/4)+1)))
    figspfft = pl.figure(figsize = (10,(int(lmax/4)+1)))
    #figspgood = pl.figure(figsize = (10,(int(lmax/4)+1)))
    axsp = []
    axspfft = []    
    goodcounter = 0

    for i, Xc in enumerate(timeseries):
        stdtimeseries = (Xc-Xc.mean())/Xc.std()
        stdbs = (bs[i]-bs[i].mean())/bs[i].std()
#        print ("here", min(stdbs),  max(stdbs), np.mean(stdbs), np.std(stdbs))
        color, alpha = 'k', 0.3
        axsp.append(figsp.add_subplot(lmax,2,(i*2+1)))
        sparklines(stdbs, '%d'%i,
                   axsp[-1], color=color, alpha=alpha, nolabel=True)
        if not fft:
            axspfft.append(figspfft.add_subplot(lmax,2,(i*2+1)))
            power = np.abs(np.fft.rfft(stdbs))[2:-5]
#            print (power)
            xmaxs, xmin = sparklines(power, '%d'%i,
                                     axspfft[-1], x=xfreq[2:-5], color=color,
                                     alpha=alpha)
            ymin, ymax = axspfft[-1].get_ylim()
            axspfft[-1].plot([0.25,0.25],[ymin, ymax],'k-')
#            print ("\r freq max",xmaxs, end='')
            sys.stdout.flush()


        axsp.append(figsp.add_subplot(lmax,2,(i*2+2)))        

        if not fft:
            sparklines(km.cluster_centers_[km.labels_[i]],
                   "cluster %i"%km.labels_[i], axsp[-1],
                   color=color, alpha=alpha)
            axspfft.append(figspfft.add_subplot(lmax,2,(i*2+2)))
            xmaxs, xmin = sparklines(np.abs(np.fft.rfft(km.cluster_centers_[km.labels_[i]])[2:-5]),
                       "cluster %i"%km.labels_[i], axspfft[-1],
                       x=xfreq[2:-5], color=color, alpha=alpha)
            #=print (xmaxs)            
            ymin, ymax = axspfft[-1].get_ylim()
            axspfft[-1].plot([0.25,0.25],[ymin, ymax],'k-')
        else:
            sparklines(transformed[km.labels_[i]][2:-5],
                       "cluster %i"%km.labels_[i], axsp[-1],
                       color=color, alpha=alpha, maxminloc=True)
        final_good_windows = []
        if km.labels_[i] in goodkmeanlabels:
            goodcounter +=1
            color, alpha = 'Navy', 0.8
#            print ("min and max: ",min(stdbs), max(stdbs))
            sparklines(stdbs, "",
                       axsp[-2], color=color, alpha=alpha)
        
            if not options.fft:
                sparklines(km.cluster_centers_[km.labels_[i]],
                   "", axsp[-1],
                                        color=color, alpha=alpha)
            else:
                sparklines(transformed[km.labels_[i]],
                       "cluster %i"%km.labels_[i], axsp[-1],
                        color=color, alpha=alpha, maxminloc=True)
            if len(freq)==2:
                print ("\r Analyzing window {0:d} of {1:d} (testing periods {2}, {3}, accepted so far {4})".format(goodcounter, ntot, freq[0], freq[1], newntot),
                   end="")
                sys.stdout.flush()

                print (" Analyzing & plotting sine window {0:d} (testing periods {1}, {2})".format(i, freq[0], freq[1]),
                       file=logfile)
            elif len(freq)==1:
                print ("\r Analyzing window {0:d} of {1:d} (testing periods {2}, accepted so far {3}))".format(goodcounter, ntot, freq[0], newntot),
                   end="")
                sys.stdout.flush()

                print (" Analyzing & plotting sine window {0:d} (testing periods {1})".format(i, freq[0]),
                       file=logfile)                

            #print  (km.labels_[i] ,  goodkmeanlabels,  km_freqs.keys())
            j = j+1
            
        
            phases[0][i], phases[5][i], thiswave = fit_freq(freq[0], stdbs)

            #print (min(thiswave), max(thiswave), freq[0],
            #       min(stdbs), max(stdbs))
            sparklines(thiswave,  "          %.2f"%(phases[5][i]),
                           axsp[-2], color='r', alpha=0.3, nolabel=True)
            fq = freq[0]
            if phases[5][i] > chi2thr and len(freq)>1:
                phases[0][i], phases[5][i], thiswave = fit_freq(freq[1], stdbs)
                     
                #print (min(thiswave), max(thiswave), freq[1],
                #       min(stdbs), max(stdbs))
                #sparklines(thiswave,  "                   %.2f"%(phases[5][i]),
                #               axsp[-2], color='y', alpha=0.3, nolabel=True)
                fq = freq[0]
                if phases[5][i] > chi2thr:
                    print ("\tbad chi square fit to sine wave: %.2f"\
                           %(phases[5][i]),
                           file=logfile)
                    continue
                
            phases[1][i] = i
            phases[2][i] = allights[i][0]
            phases[3][i] = allights[i][1]
            phases[4][i] = km.labels_[i]
            print ("here", ntot/2+1, newntot+1)
            ax.append(fig.add_subplot(max(ntot/2+1, newntot+1), 1, (newntot+1)))
            
            ax[-1].plot(np.arange(stdbs.size) * options.sample_spacing,
                        stdbs, label="%.2f %.2f"%(phases[2][i], phases[3][i]))
            ax[-1].plot(np.arange(stdbs.size) * options.sample_spacing,
                        thiswave,
                        label="%.2f %.2f"%\
                        (phases[0][i], phases[5][i]))
        

            newntot += 1
            ax[-1].legend(frameon=False, fontsize=10)
            
            #print ("final freq, phase", freq, phi0)
            
            #sinelights = [[783,1095,2]]#, [693,1099,1], [693,1123,3],
            #      [780,1127,4],[1233,1099,5],
            #      [1280,1135,7],[1280,1083,8],[46,1115,20],
            #      [559,1001,49],[515,1269,51],[429,1182,53],
            #      [791,870,54],[984,579,58],
            #      [921,248,59],[1414,957,70],[1414,981,76],
            #      [1481,957,77],
            #      [1883,508,105],[2080,1269,121]]
                
            
            makeGifLcPlot(phases[2][i], phases[3][i], i,
                          stdtimeseries,
                          aperture, filepattern,
                          imsize, flist,
                          showme = showme,
                          fft = fft,
                          stack = stack, outdir=outdir0)
    
            x1,x2=int(phases[2][i])-aperture*3,\
                   int(phases[2][i])+aperture*3
            y1,y2=int(phases[3][i])-aperture*3,\
                   int(phases[3][i])+aperture*3
            axs1.plot([x1,x2],[y1,y1], '-',
                      color='%s'%kelly_colors_hex[km.labels_[i]])    
            axs1.plot([x2,x2],[y1,y2], '-',
                      color='%s'%kelly_colors_hex[km.labels_[i]])    
            axs1.plot([x1,x2],[y2,y2], '-',
                      color='%s'%kelly_colors_hex[km.labels_[i]])    
            axs1.plot([x1,x1],[y2,y1], '-',
                      color='%s'%kelly_colors_hex[km.labels_[i]])

            print("here")
            print ("%d,%.2f,%.2f,%.2f,%.2f"%(i, phases[2][i], phases[3][i], phases[0][i], phases[5][i]),
                   file=outphasesfile)

            goodphases = phases[phases[5][i] > chi2thr]
            #np.save(goodcoordsoutfile, goodphases)
            #
    if not fft: 
        fignamekm = outdir + "/" + fnameroot + "_km_assignments.pdf"
        fignamegw = outdir + "/" + fnameroot + "_goodwindows.pdf"
        fignamefft = outdir + "/" + fnameroot + "_transform.pdf" 
        fignamegwf = outdir + "/" + fnameroot + "_goodwindows_fits.pdf"
    else: 
        fignamekm = outdir + "/" + fnameroot + "_km_assignments_fft.pdf"
        fignamegw = outdir + "/" + fnameroot + "_goodwindows_fft.pdf"
        fignamegwf = outdir + "/" + fnameroot + "_goodwindows_fits_fft.pdf"
        
    try:
        figsp.savefig(fignamekm)
        if not fft:
             figspfft.savefig(fignamefft)
    except ValueError: 
        print ("could not save figure %s or %s"%(figname, fignamefft))
    pl.close(figsp)
    pl.close(figspfft)
    
    print ("")
    if newntot == 0:
        print ("\n   !!!No windows with the right time behavior!!!")
        return [-1], [-1]
        #sys.exit()
    axs1.set_title("%d good windows"%newntot)

    try:
        fig2.savefig(fignamegw)
    except ValueError: 
        print ("could not save figure %s"%figname)    
    pl.close(fig2)

    ax[-1].set_xlabel("seconds")
    try:
        fig.savefig(fignamegwf)
    except ValueError: 
        print ("could not save figure %s"%figname)
    pl.close(fig)
    print ("\nActual number of windows well fit by a sine wave (chisq<1): %d"%newntot)
    #sys.exit()
  
    outphasesfile.close()

    return phases, goodphases


def tryrunit((arg, options)):
    try: 
        res = runit((arg, options))
        return res
    except: 
        print ("One failed run...")
        return None

def runit((arg, options)):
    filepattern = arg
    impath = os.getenv("UIdata") + filepattern
    print ("\n\nUsing image path: %s\n\n"%impath)

    img = glob.glob(impath+"*0000.raw")[0]
    print (img)
    fnameroot = filepattern.split('/')[-1]


    if options.stack:
        print ("(There is a stack", options.stack,")")
        stack = np.load(options.stack)
        imsize  = findsize(stack,
                           filepattern=options.stack.replace('.npy','.txt'))
    else:
        imsize  = findsize(img, filepattern=filepattern)
        stack = np.fromfile(img,dtype=np.uint8).reshape(imsize['nrows'],
                                                       imsize['ncols'],
                                                       imsize['nbands'])
            
    
    print ("Image size: ", imsize)
        
    flist = sorted(glob.glob(impath+"*.raw"))

    print ("Total number of image files: %d"%len(flist))

    nmax = min(options.nmax, len(flist)-options.skipfiles)
    print ("Number of timestamps (files): %d"%(nmax))
    if nmax<30: return 0
    flist = flist[options.skipfiles:nmax+options.skipfiles]    

    if options.coordfile:
        print (options.coordfile)
        try:
            allights = np.load(options.coordfile)
        except:
            print ("you need to create the window mask, you can use windowFinder.py")
            print (options.coordfile)
            return (-1)
    elif os.path.isfile(filepattern+"_allights.npy"):
        try:
            allights = np.load(filepattern+"_allights.npy")
        except:
            print ("you need to create the window mask, you can use windowFinder.py")
            print (filepattern+"_allights.npy")
            return (-1)
    else:
        print ("you need to create the window mask, you can use windowFinder.py")
        print (filepattern+"_allights.npy")
        return (-1)
        
        
    lmax = len(allights)
    if options.lmax: lmax = min([lmax, options.lmax])
    print ("Max number of windows to use: %d"%lmax)
    outdir0 = '/'.join(filepattern.split('/')[:-1])+'/N%04dS%04d'%(nmax,  options.skipfiles)
    outdir = '/'.join(filepattern.split('/')[:-1])+'/N%04dW%04dS%04d'%(nmax,
                                                                 lmax,
                                                                 options.skipfiles)
    if not os.path.isdir(outdir):
        subprocess.Popen('mkdir -p %s '%outdir, shell=True)
        #os.system('mkdir -p %s '%outdir)
    if not os.path.isdir(outdir0):
        subprocess.Popen('mkdir -p %s/%s'%(outdir0+'pickles'), shell=True)
        #os.system('mkdir -p %s'%outdir0+"/pickles")
        subprocess.Popen('mkdir -p %s/%s'%(outdir0+'gifs'), shell=True)
        #os.system('mkdir -p %s'%outdir0+"/gifs")
    print ("Output directories: ",
           '/'.join(filepattern.split('/')[:-1]), outdir0, outdir)

    if (os.path.getsize(filepattern+".log"))>100000:
        print (os.path.getsize(filepattern+".log"), filepattern+".log")
        print ('tail -1000 %s > tmplog | mv tmplog %s'%(filepattern+".log", filepattern+".log"))
        try: subprocess.Popen('tail -1000 %s > tmplog | mv tmplog %s'%(filepattern+".log", filepattern+".log"))
        except OSError: pass
    logfile = open(filepattern+".log", "a")
    print ("Logfile:", logfile)
    print ("\n\n\n\t\t%s"%str(datetime.datetime.now()), file=logfile)
    print ("options and arguments:", options,
           arg, file=logfile)
    xfreq = np.fft.rfftfreq(nmax, d=options.sample_spacing)    
    if options.fft:
        bsoutfile = outdir + "/" + fnameroot + "_bs_fft.npy"
        coordsoutfile = outdir + "/" + fnameroot + "_coords_fft.npy"
        goodcoordsoutfile = outdir + "/" + fnameroot + "_goodcoords_fft.npy"                
        kmresultfile = outdir + "/" + fnameroot + "_kmresult_fft.pkl"
        pcaresultfile = outdir + "/" + fnameroot + "_PCAresult_fft.pkl"        

        
    else:
        bsoutfile = outdir + "/" + fnameroot + "_bs.npy"
        coordsoutfile = outdir + "/" + fnameroot + "_coords.npy"
        goodcoordsoutfile = outdir + "/" + fnameroot + "_goodcoords.npy"
        kmresultfile = outdir + "/" + fnameroot + "_kmresult.pkl"
        pcaresultfile = outdir + "/" + fnameroot + "_PCAresult.pkl"        

    figspk = pl.figure(figsize = (10,(int(lmax/2)+1)))
    ax = []
    figspkfft = pl.figure(figsize = (10,(int(lmax/2)+1)))
    axfft = []
    
    bs = np.zeros((lmax, nmax))
    fs = np.zeros((lmax, int(nmax/2+1)))
    badindx = []


    print ("")

    if READ and os.path.isfile(bsoutfile) and \
       os.path.isfile(coordsoutfile):
        print ("reading old data file", bsoutfile)
        bs = np.load(bsoutfile)
        allights = np.load(coordsoutfile)
    else:
        #this is tricky: parallelize the extraction only if you are not
        #parallelizing the image sequencies (i.e. nbursts=1)
        if options.nps > 1 and options.nbursts == 1 and not NOPARALLEL:
            print ("\n\n\nrunning on %d threads\n\n\n"%options.nps)
            pool = mpc.Pool(processes=options.nps)
            primargs = np.array(zip(allights[:lmax], range(lmax)))
            #print (primargs)
            #sys.exit()
            secondargs = [xfreq, lmax, filepattern,
                          imsize, outdir0, options, figspk, ax, figspkfft, axfft]
            for iii in (itertools.izip(primargs, itertools.repeat(secondargs))):
                print (iii)
            ##pool.map(runit, (itertools.izip(args, itertools.repeat(options))))
            pool.map(extraction, (itertools.izip(primargs, itertools.repeat(secondargs))))
            #bs_fs = np.array(bs_fs)
            #print (bs_fs.shape)
            return (-1)
            #sys.exit()
        else:
            for i,cc in enumerate(allights[:lmax]):

                print ("\r### Extracting window {0:d} of {1:d} (x={2:d}, y={3:d})"\
                       .format(i+1, lmax, int(cc[0]),  int(cc[1])), end="")
                sys.stdout.flush()
                bs[i], fs[i] = extraction(((cc, i), xfreq, lmax,
                                          flist, filepattern,
                                          imsize, outdir0,
                                          options, figspk, ax,
                                          figspkfft, axfft))
                ax.append(figspk.add_subplot(lmax/2+1,2,i+1))
        '''            

                #if False:    
                bs[i], fs[i]  = get_plot_lca ((int(cc[0]+0.5)-options.aperture,
                                          int(cc[1]+0.5)-options.aperture, 
                                          int(cc[0]+0.5)+options.aperture+1,
                                          int(cc[1]+0.5)+options.aperture+1),
                                          flist, 
                                          filepattern+'_x%d_y%d_ap%d'%(int(cc[0]+0.5),
                                                                       int(cc[1]+0.5), 
                                                                       options.aperture),
                                          imsize, fft=options.fft,
                                          verbose=False, showme=options.showme,
                                          outdir = outdir0)

                #pl.plot(b1)
                #print (bs[i].size)
            
                sparklines(bs[i], '%d %d:%d'%(i, int(cc[0]), int(cc[1])), ax[i])
                if options.fft:
                    axfft.append(figspkfft.add_subplot(lmax/2+1,2,i+1))                
                    sparklines(fs[i][2:-5], '%d %d:%d'%(i, int(cc[0]), int(cc[1])),
                               axfft[-1], x=xfreq[2:-5],
                               maxminloc=options.fft)
        '''
        print ("")

        ax[0].text (0.2, 1.2, '{0:1d} seconds           {1:2s}'\
                    .format(len(bs[0])*4,'min/max'), 
                    transform = ax[0].transAxes, fontsize=15)


        ax[1].text (0.2, 1.2, '{0:1d} seconds           {1:2s}'\
                    .format(len(bs[0])*4,'min/max'), 
                transform = ax[1].transAxes, fontsize=15)

        figname = outdir + "/" + fnameroot + "_sparklines_lcv.pdf"
        try: 
            figspk.savefig(figname)
        except ValueError:
            print ("could not save", figname)
        pl.close(figspk)   

        if options.fft:
            figname = outdir + "/" + fnameroot + "_sparklinesfft_lcv.pdf"
            try: 
                figspkfft.savefig(figname)
            except ValueError:
                print ("could not save", figname)
        pl.close(figspkfft)   
            
        if options.showme: pl.show()

        badindx = []
        for i,bsi in enumerate(bs):
            #print (bsi)
            if np.isnan(bsi).any():
                badindx.append(i)

        print ("\n### Removing bad indices if any:", badindx, len(allights))            
        if len(badindx)>0:
            bsnew = np.delete(bs, badindx, 0)
            bs = bsnew

            allightsnew = np.delete(allights[:lmax],  badindx, 0)
            allights = allightsnew[:lmax-len(badindx)]
            fsnew = np.delete(fs, badindx, 0)
            fs = fsnew

        else: allights = allights[:lmax]
        np.save(coordsoutfile, allights)
        np.save(bsoutfile, bs)
        
    print ("Windows now:", len(bs))
    img = np.fromfile(flist[0],dtype=np.uint8).reshape(imsize['nrows'],
                                                       imsize['ncols'],
                                                       imsize['nbands'])
    

    if options.readKM and os.path.isfile(kmresultfile):
        try: 
            print ("reading KM result from saved file %s"%kmresultfile)
            kmresult = pkl.load(open(kmresultfile))
        except ValueError:
            print ("wrong pickle protocol. remove ",kmresultfile)
            return (-1)
    #sys.exit()
            
    else:

         print ("\n### Starting PCA")

         if not options.fft:
             timeseries = bs
             #print (timeseries.shape)
             x = np.arange(timeseries.shape[0])
         else:
             timeseries = fs

         lts = len(timeseries)
         #pl.figure()
         #print (bs.shape)
         #[pl.plot(bs[i], alpha=0.1) for i in range(len(bs))]
         #pl.show()

         pca = PCA()
         X_pca = pca.fit_transform(timeseries)
         pca.fit(timeseries)

         evals = pca.explained_variance_ratio_
         evals_cs = evals.cumsum()
         evecs = pca.components_

         figrows = min(60,(int(lts/2)+1))
         figpca = pl.figure(figsize = (10, figrows))
         spax = []
         
         if options.fft:
             for i,Xc in enumerate(evecs):
                 spax.append(figpca.add_subplot(figrows, 2, i+1))
                 sparklines(Xc, "%.3f"%evals_cs[i], spax[i],
                            x=xfreq, maxminloc=options.fft)
                 if evals_cs[i] > 0.9 or i+1 == figrows * 2:
                     break
         else:
             for i,Xc in enumerate(evecs):
                 spax.append(figpca.add_subplot(figrows, 2, i+1))
                 sparklines(Xc, "%.3f"%evals_cs[i], spax[i], twomax=False,
                            maxminloc=options.fft)
                 if evals_cs[i] > 0.9 or i+1 == figrows * 2:
                     break
                
             
             
         pkl.dump(pca, open(pcaresultfile, "wb"))

         print ("Number of PCA component to reconstruct 90% signal: {0}".format(i+1))
         
         if not options.fft: figname = outdir + "/" + fnameroot + "_PCA.pdf"
         else: figname = outdir + "/" + fnameroot + "_PCA_fft.pdf"

         figpca.savefig(figname)

         if PCAonly: return(0)


         print ("\n### Starting K-Means clustering")

         #Note: the first and second PCA components are the sine waves 180 deg phase shifted.
         #If I want to make a model for the saturated waves i can use those. does not really work unless there are several saturated lights

         kmcenters = evecs[:options.nkmc].copy()
         if not options.fft:
             kmcenters[-1] = evecs[0]*10<0.5

             kmcenters[-2] = evecs[1]*10<0.5
         #print (evecs)
         km = KMeans(n_clusters=options.nkmc, init=evecs[:options.nkmc])
         vals = ((timeseries.T - timeseries.mean(1))/timeseries.std(1)).T
         km.fit(vals)


         print ("\n### Determining phase for selected windows")
         fig = pl.figure(figsize = (10,10))
         kmax = []
         goodkmeanlabels, km_freqs = [], {}
         transformed = []
         for i,Xc in enumerate(km.cluster_centers_):
             kmax.append(fig.add_subplot(20,2,(i*2+1)))
             if not options.fft:
                 sparklines(Xc, "%i (%d)"%(i, len(km.labels_[km.labels_==i])), kmax[-1])
                 kmax.append(fig.add_subplot(20,2,(i*2+2)))
                 transformed.append( np.abs(np.fft.rfft(Xc))[1:])
                 transformed[-1][0] = 0
                 km_xmax, km_xmin = sparklines(transformed[-1][:-5], "", kmax[-1],
                                               x=xfreq[1:-5])
             else:
                 kmax.append(fig.add_subplot(20,2,(i*2+2)))
                 #print (Xc[1:-5])
                 km_xmax, km_xmin = sparklines(Xc[1:-5], "%i"%i, kmax[-1],
                                               x=xfreq[1:-5], maxminloc=True)
                 transformed.append(np.abs(np.fft.irfft(Xc)))
                 sparklines(transformed[-1], "", kmax[-2])

             accepted = ''

             if np.abs(km_xmax[0] - 0.25) < 0.08:
                 goodkmeanlabels.append(i)
                 km_freqs[i] = km_xmax[0]
                 accepted = "ACCEPTED!"            
             elif np.abs(km_xmax[1] - 0.25) < 0.08 :
                 goodkmeanlabels.append(i)
                 km_freqs[i] = km_xmax[1]            
                 accepted = "ACCEPTED!"
                 
             print ("cluster {0}: strongest frequecies {1}, {2} - {3}".\
                    format(i,
                           km_xmax[0],
                           km_xmax[1], accepted))


             ymin, ymax = kmax[-1].get_ylim()
             kmax[-1].plot([0.25,0.25],[ymin, ymax],'k-')
             #kmax[-1].text(0.8,0.8,"cluster %i"%i,
             #              color=kelly_colors_hex[i],
             #              transform=ax[-1].transAxes)

         print (" All labels: ", km.labels_, file=logfile)
         print (" Good labels:", goodkmeanlabels, file=logfile)

         
         if not options.fft: figname = outdir + "/" + fnameroot + "_KM.pdf"
         else: figname = outdir + "/" + fnameroot + "_KM_fft.pdf"
         pl.savefig(figname)
         pl.close(fig)
         
         transformed = np.array(transformed)

         fig = pl.figure()
         axs = fig.add_subplot(311)
         axs0 = fig.add_subplot(312)
         axs1 = fig.add_subplot(313)    


         axs.imshow(stack,  interpolation='nearest')
         axs.set_xlim(0, axs.get_xlim()[1])
         axs.set_ylim(axs.get_ylim()[0], 0)
         axs0.imshow(img,  interpolation='nearest')
         axs0.set_xlim(0, axs0.get_xlim()[1])
         axs0.set_ylim(axs0.get_ylim()[0], 0)
         axs1.imshow(img,  interpolation='nearest')
         axs1.set_xlim(0, axs1.get_xlim()[1])
         axs1.set_ylim(axs1.get_ylim()[0], 0)

         for i,cc in enumerate(allights):
             x1,x2=int(cc[0])-options.aperture*3,\
                    int(cc[0])+options.aperture*3
             y1,y2=int(cc[1])-options.aperture*3,\
                    int(cc[1])+options.aperture*3
             #axs0.plot([x1,x2],[y1,y1], '-',
             #         color='%s'%kelly_colors_hex[km.labels_[i]])    
             #axs0.plot([x2,x2],[y1,y2], '-',
             #         color='%s'%kelly_colors_hex[km.labels_[i]])    
             #axs0.plot([x1,x2],[y2,y2], '-',
             #         color='%s'%kelly_colors_hex[km.labels_[i]])    
             #axs0.plot([x1,x1],[y2,y1], '-',
             #         color='%s'%kelly_colors_hex[km.labels_[i]])
             axs1.plot([x1,x2],[y1,y1], '-', lw=0.3,
                      color='%s'%kelly_colors_hex[km.labels_[i]])    
             axs1.plot([x2,x2],[y1,y2], '-', lw=0.3,
                      color='%s'%kelly_colors_hex[km.labels_[i]])    
             axs1.plot([x1,x2],[y2,y2], '-', lw=0.3,
                      color='%s'%kelly_colors_hex[km.labels_[i]])    
             axs1.plot([x1,x1],[y2,y1], '-', lw=0.3,
                       color='%s'%kelly_colors_hex[km.labels_[i]])
             R = np.sum(img[y1:y2,x1:x2,0].astype(float))
             G = np.sum(img[y1:y2,x1:x2,1].astype(float))
             B = np.sum(img[y1:y2,x1:x2,2].astype(float))
             norm = np.array([R,G,B]).max()
             if norm>0 and not np.isnan(norm):
                 #print (norm, R, G, B, R/norm, G/norm, B/norm)
                 axs0.plot(int(cc[0]),int(cc[1]), 'o',
                       color=(R/norm, G/norm, B/norm), ms=2, alpha=0.8)    

             #print (km.labels_[i], '{0:.2f} {1:.2f} {2:.2f}'.format(R/norm, G/norm, B/norm))
             #axs2.scatter(km.labels_[i], sum(img[y1:y2,x1:x2,:]), s=60, 
             #         color = (R/norm, G/norm, B/norm), alpha=0.8)  

         axs.set_title("stack", fontsize=10)
         axs0.set_title("windows by RBG color", fontsize=10) 
         axs1.set_title("windows by K-means cluster", fontsize=10)
         axs.axis('off')
         axs0.axis('off')
         axs1.axis('off')    

         figname = outdir + "/" + fnameroot + "_windows.pdf"
         #pl.show()
         fig.savefig(figname)
         pl.close(fig)
         #fig2.savefig(filepattern + "_kmclusters_brightness.png")

         phi0 = 0
         ntot = 0
         for i in goodkmeanlabels:#[1,3,4,6,8,9]:#[1,2,3,4,7]: 
             ntot += sum(km.labels_ == i)
         print ("Total number of lights with sine behavior: %d (fraction: %.2f)"%(ntot, np.float(ntot)/lmax))
         if ntot == 0:
             print ("   !!!No windows with the right time behavior!!!")
             return (-1)
             #sys.exit()

         
         #print (km_freqs)
         kmresult = {'timeseries':timeseries,
                     'transformed':transformed,
                     'km':km, 'km_freqs':km_freqs,
                     'goodkmeanlabels':goodkmeanlabels,
                     'ntot':ntot}
    
         pkl.dump(kmresult, open(kmresultfile, "wb")) 
    
    
    
    goodphases, phases = fit_waves(filepattern, lmax, nmax, kmresult['timeseries'],
                       kmresult['transformed'], kmresult['km'],
                       kmresult['goodkmeanlabels'], kmresult['ntot'],
                       img, fnameroot, kmresult['km_freqs'],
                       stack, bs, logfile, allights,
                       options.aperture, imsize, flist, xfreq, options.chi2,
                       fft=options.fft, showme=options.showme,
                       outdir=outdir, outdir0=outdir0)
    try:
        if goodphases == [-1] and phases==[-1]:
            return (-1)
    except:
        pass

    np.save(goodcoordsoutfile, goodphases)
    ax = pl.figure().add_subplot(111)
    try:
        for i in set(phases[1][~np.isnan(phases[0])]):
            pl.plot(i, np.mean(phases[0][phases[1]==i]/np.pi), 
                    'o', ms=sum(phases[1]==i)*5, alpha=0.3)
            pl.plot(phases[1], phases[0]/np.pi, 'o')
            ax.set_xlim(-0.5,9.5)
            ax.set_xlabel("K-means cluster")
            ax.set_ylabel(r"phase ($\pi$)")
    except TypeError: pass
    if options.fft: figname = outdir + "/" + fnameroot + "_km_phases_fft.png"
    else:  figname = outdir + "/" + fnameroot + "_km_phases.png"

    try:
        pl.savefig(figname)
    except ValueError: 
        print ("could not save figure %s"%figname)    
    pl.close()
    
    ax = pl.figure().add_subplot(111)
    cmap =  pl.cm.rainbow(phases[0][~np.isnan(phases[0])])
    #print (len(cmap), len(phases[0][~np.isnan(phases[0])]), cmap)

    #cmap = cm.rainbow
    #cs1 = [colors[i] for i in range(len(phases[0]))] 
    #for p in range(len(phases[0])):
    #    pl.scatter(phases[2][p], phases[3][p], color = cmap(len(phases[0]) / float(phases[0][p])))
    pl.scatter(phases[2][~np.isnan(phases[0])], phases[3][~np.isnan(phases[0])], color = cmap)
    ax.get_axes().set_aspect('equal', 'datalim')


    if not options.fft: pl.savefig(outdir + "/" + fnameroot + "_phases.png") 
    else: pl.savefig(outdir + "/" + fnameroot + "_phases_fft.png")
    #ax.axis('off')
    #pl.show()
    pl.close()
    return 0


if __name__=='__main__':

    parser = optparse.OptionParser(usage="getallcv.py 'filepattern' ",
                                   conflict_handler="resolve")
    parser.add_option('--nmax', default=100, type="int",
                      help='number of images to process (i.e. timestamps)')
    parser.add_option('--lmax', default=None, type="int",
                      help='number of lights')
    parser.add_option('--showme', default=False, action="store_true",
                      help='show plots')
    parser.add_option('--aperture', default=2, type="int",
                      help="window extraction aperture (1/2 side)")
    parser.add_option('--chi2', default=1.0, type="float",
                  help="chi square threshold")    
    parser.add_option('--nkmc', default=10, type="int",
                      help='number of KMeans clusters')
    parser.add_option('--sample_spacing', default=0.25, type="float",
                      help="camera sample spacing (inverse of sample rate)")
    parser.add_option('--coordfile', default=None, type="str",
                      help='coordinates python array (generated by windowFinder.py)')
    parser.add_option('--stack', default=None, type="str",
                      help='stack python array')
    parser.add_option('--nps', default=None, type="int",
                      help='number of cores to use')
    parser.add_option('--nbursts', default=None, type="int",
                      help='number of bursts. leave this alone: it will be set t to the number of arguments passed')        
    parser.add_option('--skipfiles', default=150, type="int",
                      help="number of files to skip at the beginning")
    parser.add_option('--readKM', default=False, action="store_true",
                      help="rereading old KM result instead of redoing it")
    parser.add_option('--fft', default=False, action="store_true",
                      help='custer in fourier space')
    
    options,  args = parser.parse_args()
    
    print ("options", options)
    print ("args", args, args[0])
    if len(args) < 1:
        sys.argv.append('--help')
        options,  args = parser.parse_args()
           
        sys.exit(0)
    if not options.nbursts:
        options.nbursts = len(args)
        
    if not options.nps:
        options.nps = mpc.cpu_count()-1 or 1
    
    if options.nps > 1 and options.nbursts > 1 and not NOPARALLEL:
        print ("\n\n\nrunning on %d threads\n\n\n"%options.nps)
        pool = mpc.Pool(processes=options.nps)
        print (type(itertools.izip(args, itertools.repeat(options))))
        print (pool.map(tryrunit, (itertools.izip(args, itertools.repeat(options)))))
    else:
        for arg in args:
            runit((arg, options))
    