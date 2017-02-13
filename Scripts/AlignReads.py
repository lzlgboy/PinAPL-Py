#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on Mon May 16 19:11:28 2016

@author: philipp
"""

# Perform alignment, count & normalize reads
# =======================================================================
# Imports
from __future__ import division # floating point division by default
import pandas as pd
from Bowtie2 import RunBowtie2
import yaml
import os
import glob
import time
import sys
from collections import Counter
from joblib import Parallel, delayed
import multiprocessing
import numpy

def CountReadsPerGene(g):
    global UniqueGeneList
    global LibGenes
    global ReadsPerGuide
    gene = UniqueGeneList[g]        
    geneIndex = [i for i,x in enumerate(LibGenes) if x==gene]
    sgCounts = [ReadsPerGuide[i] for i in geneIndex]
    g_counts = sum(sgCounts)
    return g_counts  


def MapAndCount(sample):    
    # ------------------------------------------------
    # Print header
    # ------------------------------------------------
    print('**************************************************************')
    print('PinAPL-Py: Alignment & Read Counting')
    print('**************************************************************')  
    start_total = time.time()   

    # ------------------------------------------------
    # Get parameters
    # ------------------------------------------------
    os.chdir('/workingdir/') 
    configFile = open('configuration.yaml','r')
    config = yaml.load(configFile)
    configFile.close()
    DataDir = config['DataDir']
    AnalysisDir = config['AnalysisDir']
    CutAdaptDir = config['CutAdaptDir']
    bw2Dir = config['bw2Dir']
    IndexDir = config['IndexDir']
    LibDir = config['LibDir']
    seq_5_end = config['seq_5_end']
    seq_3_end = config['seq_3_end']
    CutErrorTol = config['CutErrorTol']
    R_min = config['R_min']
    LibFilename = config['LibFilename']
    Theta = config['Theta']
    L_bw = config['L_bw']
    N_bw = config['N_bw']
    i_bw = config['i_bw']
    N0 = config['N0']
    res = config['dpi']
    AlnOutput = config['AlnOutput']
    keepCutReads = config['keepCutReads']
    ReadsDir = DataDir
    AlnStemDir = config['AlignDir']
    AlnDir = AlnStemDir+sample+'/'
    QCDir = config['QCDir']
    LogDir = QCDir+sample+'/'       
    AlnFileSuffix = '_bw2Aln.tsv'
    GuideCount_Suffix = '_GuideCounts.tsv'
    GeneCount_Suffix = '_GeneCounts.tsv'
    NormSuffix = '_0.tsv'
    
    # ------------------------------------------------
    # Apply cutadapt to trim off the constant region
    # ------------------------------------------------       
    start = time.time() 
    print('cutadapt read clipping in progress ...')        
    os.chdir(ReadsDir)
    ReadsFilename = glob.glob(sample+'*.fastq.gz')
    if len(ReadsFilename) == 2:      # A file ending in *_cut.fastq is present from a previous run
        if '_cut' in ReadsFilename[0]:
            ReadsFilename = ReadsFilename[1]
        else:
            ReadsFilename = ReadsFilename[0] 
    else:
        ReadsFilename = ReadsFilename[0]
    Reads_filename = ReadsFilename[0:-9]
    ReadsCutFilename = Reads_filename + '_cut.fastq.gz'
    ReadsCut_filename = ReadsCutFilename[0:-9]
    CutAdaptCmdLine = CutAdaptDir+'cutadapt -a '+seq_5_end+'...'+seq_3_end  \
                        +' '+ReadsFilename+' -o '+ReadsCutFilename \
                        +' -e '+str(CutErrorTol) \
                        +' --minimum-length '+str(R_min)+' > cutadapt.txt'
    os.system(CutAdaptCmdLine)
    if not os.path.exists(LogDir):
        os.makedirs(LogDir)
    mv_cmdline = 'mv cutadapt.txt '+LogDir
    os.system(mv_cmdline)
    print('cutadapt read clipping completed.')
    end = time.time()
    
    # Time stamp
    sec_elapsed = end-start
    if sec_elapsed < 60:
        time_elapsed = sec_elapsed
        print('Time elapsed (Read clipping) [secs]: ' + '%.3f' % time_elapsed +'\n')
    elif sec_elapsed < 3600:
        time_elapsed = sec_elapsed/60
        print('Time elapsed (Read clipping) [mins]: ' + '%.3f' % time_elapsed +'\n')
    else:
        time_elapsed = sec_elapsed/3600
        print('Time elapsed (Read clipping) [hours]: ' + '%.3f' % time_elapsed +'\n')    
    
    # ----------------------------------------------
    # Run Bowtie alignment
    # ----------------------------------------------                  
    start = time.time()  
    print('Bowtie2 alignment in progress ...')        
    RunBowtie2(ReadsCut_filename,ReadsDir,AlnDir,LogDir,bw2Dir,IndexDir,Theta,L_bw,N_bw,i_bw,res)
    end = time.time()
    # Time stamp
    sec_elapsed = end-start
    if sec_elapsed < 60: 
        time_elapsed = sec_elapsed
        print('Time elapsed (Alignment & Processing) [secs]: ' + '%.3f' % time_elapsed +'\n')
    elif sec_elapsed < 3600:
        time_elapsed = sec_elapsed/60
        print('Time elapsed (Alignment & Processing) [mins]: ' + '%.3f' % time_elapsed +'\n')
    else:
        time_elapsed = sec_elapsed/3600
        print('Time elapsed (Alignment & Processing) [hours]: ' + '%.3f' % time_elapsed +'\n')
    
    # --------------------------------------
    # Get read counts
    # --------------------------------------
    start = time.time()    
    print('Reads counting in progress ...')
    # Read library
    os.chdir(LibDir)
    LibCols = ['gene','ID','seq']
    LibFile = pd.read_table(LibFilename, sep = '\t', skiprows = 1, names = LibCols)
    sgIDs = list(LibFile['ID'].values)
    N_Guides = len(sgIDs)
    global LibGenes
    LibGenes = list(LibFile['gene'].values)
    N_Genes = len(set(LibGenes))
    # Read alignment file
    os.chdir(AlnDir)
    AlnFilename = ReadsCut_filename+AlnFileSuffix
    colnames = ['sgID','mapping_quality']
    AlnFile = pd.read_table(AlnFilename, sep = '\t', names = colnames)
    N_Reads = len(AlnFile)
    IDRead = list(AlnFile['sgID'].values) 
    ReadCounts = Counter()
    for ID in IDRead:
        ReadCounts[ID] += 1
    global ReadsPerGuide
    ReadsPerGuide = list()
    for ID in sgIDs:
        ReadsPerGuide.append(ReadCounts[ID])    
    
    # --------------------------------------
    # Write count files
    # --------------------------------------
    os.chdir(LogDir)     
    # Read counts per sgRNA in library
    print('Counting reads per sgRNA ...')
    GuideCountsFilename = Reads_filename + GuideCount_Suffix
    GuideCounts = open(GuideCountsFilename,'w')
    for k in range(N_Guides):
        GuideCounts.write(sgIDs[k] + '\t'+ LibGenes[k] + '\t' + str(ReadsPerGuide[k]) + '\n')
    GuideCounts.close()
    # Read counts per gene in library       
    print('Counting reads per gene ...')   
    GeneCountsFilename = Reads_filename + GeneCount_Suffix
    GeneCounts = open(GeneCountsFilename,'w')
    global UniqueGeneList
    UniqueGeneList = list(set(LibGenes))   
    G = len(UniqueGeneList)  
    num_cores = multiprocessing.cpu_count()
    ReadsPerGene = Parallel(n_jobs=num_cores)(delayed(CountReadsPerGene)(g) for g in range(G))  
    for g in range(G):
        GeneCounts.write(UniqueGeneList[g] + '\t' + str(ReadsPerGene[g]) + '\n')
    GeneCounts.close()
    # Normalization    
    print('Normalizing read counts ...')
    GuideCounts0_Filename = GuideCountsFilename[0:-4] + NormSuffix
    GuideCounts0 = open(GuideCounts0_Filename,'w')
    ReadsPerGuide_0 = list()
    for k in range(N_Guides):      
        ReadsPerGuide_0.append(int(numpy.ceil(ReadsPerGuide[k]/N_Reads*N0)))
        GuideCounts0.write(sgIDs[k] + '\t' + LibGenes[k] + '\t' + str(ReadsPerGuide_0[k]) + '\n')
    GuideCounts0.close()
    GeneCounts0_Filename = GeneCountsFilename[0:-4] + NormSuffix
    GeneCounts0 = open(GeneCounts0_Filename,'w')
    ReadsPerGene_0 = list()
    for j in range(G):    
        ReadsPerGene_0.append(int(numpy.ceil(ReadsPerGene[j]/N_Reads*N0)))
        GeneCounts0.write(UniqueGeneList[j] + '\t' + str(ReadsPerGene_0[j]) + '\n')
    GeneCounts0.close()        
    end = time.time()
    print('Reads counting completed.')
    # Time stamp
    sec_elapsed = end-start
    if sec_elapsed < 60:
        time_elapsed = sec_elapsed
        print('Time elapsed (Reads Counting) [secs]: ' + '%.3f' % time_elapsed +'\n')
    elif sec_elapsed < 3600:
        time_elapsed = sec_elapsed/60
        print('Time elapsed (Reads Counting) [mins]: ' + '%.3f' % time_elapsed + '\n')
    else:
        time_elapsed = sec_elapsed/3600
        print('Time elapsed (Reads Counting) [hours]: ' + '%.3f' % time_elapsed + '\n')

    # --------------------------------------
    # Cleaning up...
    # --------------------------------------
    start = time.time()  
    # clipped reads file    
    if not keepCutReads:
        os.chdir(ReadsDir)
        os.system('rm '+ReadsCutFilename)    
    # alignment output        
    if AlnOutput == 'Compress':
        print('Compressing raw alignment output...')
        os.chdir(AlnDir)
        # converting SAM to BAM
        SAM_output = glob.glob(sample+'*bw2output.sam')[0]
        BAM_output = SAM_output[:-3] + 'bam'
        os.system('samtools view -buSH '+SAM_output+' > '+BAM_output)
        os.system('rm '+SAM_output)
        # compressing SAM table
        SAM_table = glob.glob(sample+'*alignments.txt')[0]
        os.system('tar -cvf - '+SAM_table+' | gzip -5 - > '+sample + '_SAM_alignments.tar.gz ')
        os.system('rm '+SAM_table)
    elif AlnOutput == 'Delete':
        print('Removing raw alignment output...')
        os.chdir(AlnDir)
        SAM_output = glob.glob(sample+'*bw2output.sam')[0]
        SAM_table = glob.glob(sample+'*alignments.txt')[0]        
        os.system('rm '+SAM_output+' '+SAM_table)
    else:
        print('Skipping raw alignment output compression/removal ...')
    end = time.time()
    # Time stamp
    sec_elapsed = end-start
    if sec_elapsed < 60: 
        time_elapsed = sec_elapsed
        print('Time elapsed (Clean-up) [secs]: ' + '%.3f' % time_elapsed +'\n')
    elif sec_elapsed < 3600:
        time_elapsed = sec_elapsed/60
        print('Time elapsed (Clean-up) [mins]: ' + '%.3f' % time_elapsed +'\n')
    else:
        time_elapsed = sec_elapsed/3600
        print('Time elapsed (Clean-up) [hours]: ' + '%.3f' % time_elapsed +'\n')     

    # --------------------------------------
    # Final time stamp
    # --------------------------------------        
    end_total = time.time()
    # Final time stamp
    print('------------------------------------------------')
    print('Script completed.')    
    sec_elapsed = end_total - start_total
    if sec_elapsed < 60:
        time_elapsed = sec_elapsed
        print('Time elapsed (Total) [secs]: ' + '%.3f' % time_elapsed +'\n')
    elif sec_elapsed < 3600:
        time_elapsed = sec_elapsed/60
        print('Time elapsed (Total) [mins]: ' + '%.3f' % time_elapsed +'\n')
    else:
        time_elapsed = sec_elapsed/3600
        print('Time elapsed (Total) [hours]: ' + '%.3f' % time_elapsed +'\n')            
      
if __name__ == "__main__":
    input1 = sys.argv[1]
    MapAndCount(input1)
