# Cardiac ring tissue contractility analysis
Based on the openly available MATLAB code from ```MagSeguret/MotionAnalysisRingShapedTissues```

Seguret Magali, Davidson Patricia, Robben Stijn, Jouve Charlène, Pereira Céline, Cerveau Cyril, Le Berre Maël, Rodrigues Ribeiro Rita S., Hulot Jean-Sébastien (2023) A versatile high-throughput assay based on 3D ring-shaped cardiac tissues generated from human induced pluripotent stem cell derived cardiomyocytes eLife 12:RP87739, https://doi.org/10.7554/eLife.87739.1.

## Purpose
Processes a set of .nd2 movies of cardiac ring tissues and produces contractility measurements for each movie.
This approach is a scalable, high throughput pipeline developed for analyzing contractility in 3D cardiomyocyte ring tissues. It offers advantages over traditional engineered heart tissue systems that are often costly, low throughput, and utilize proprietary software that can be difficult to use and produce inconsistent results.


## Functionality added to the MATLAB code
The main functionality developed in our pipeline is that the code is now in python, an open source software, instead of MATLAB which is proprietary and closed source. Our changes have also made the pipeline easier for users to input files (directly using .nd2 instead of needing to convert to .mp4) and is able to process almost all movies the pipeline is given by automatically thresholding the movies instead of frequently rejecting data. 

We have also increased the readouts and measurements saved by the pipeline, including an image of the mask, force (nN), contraction and relaxation velocity, and runtime logging. 

Importantly, we have developed our pipeline to be scalable and high throughput, working entirely on Terra and Google Cloud Platform. The pipeline script can easily be run locally, however, using the distributed WDL we have developed, it is also possible to distributedly process movies directly from a Google Cloud bucket and also save the results there. We also have functions in ```Utils.py``` that can help with post processing and QC.


## How to use
The pipeline can be run either locally or on Terra (either sequential or distributed). The outputs will be the same either way.

Outputs:
* ```ExportVal_Tissues_Motion_analysis.csv```: contains the overall metrics and mean values for the movie, including metrics about the file, tissue coverage/uniformity, contraction frequency and contraction and relaxation velocity
*  ```cycles.csv```: contains cycle level information including contraction and relaxation time for each peak
*  ```FrameByFrameResults.csv```: contains results per each frame of the movie. Most importantly stress_mNmm2 and force_nN
*  ```mask.png```: An image of the mask created of the tissue. Can use to easily reference what the tissue looks like without having to open up the .nd2 movie
*  ```runtime_log.txt```: log from running the pipeline including if any errors came up during the calculations. Can be useful for movies that only contract once and therefore have NaN for a lot of the metrics
  
### Locally
1. git clone this repo and ensure all the necessary dependencies are installed (see ```requirements.txt```)
   
To process and entire folder, from ```sequential_ring_tissue_script.py``` call ```motion_analysis(input_folder, output_folder, pixel_size_um, diameter_um, E, frame_rate)```

To process a single movie, from ```distributed_ring_tissue_script.py``` call ```def motion_analysis(file_path, output_folder, pixel_size_um, diameter_um, E, frame_rate)```

The only difference between these two scripts is that one is set up to process an entire folder and the other only processes one file. The outputs will be the same.

### On Terra
1. The ```ring-tissue-analysis``` workspace has been set up on Terra with the necessary WDLs (from the DockStore and pulled from this repo)

To run sequentially and entire folder, call the WDL ```sequential_analysis``` and include the gsurl to the data, the output bucket, and the values for the pixel_size_um, diameter_um, E (Pa) and frame_rate.

To run a folder (or multiple levels of folders) distributedly, call the WDL ```distributed_analysis``` and include the gsurl to the data, the output bucket, and the values for the pixel_size_um, diameter_um, E (Pa) and frame_rate.

### Calcium analysis
Additionally, we have developed a version of the analysis pipeline to process ring tissues with calcium imaging. The ```calcium_processing_script``` is run with the same commands as above. 

Along with all of the previous outputs, the ```FrameByFrameResults.csv``` also includes the column Ring_Intensity_Normalized```. For each frame this is calculated as (the frame intensity - mean intensity of the movie) / mean intensity of the movie. This column can then be used to plot the ring intensity over time.


