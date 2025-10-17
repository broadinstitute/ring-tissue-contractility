version 1.0

## Copyright Broad Institute, 2021
##
## LICENSING :
## This script is released under the WDL source code license (BSD-3)
## (see LICENSE in https://github.com/openwdl/wdl).

task ring_tissue_folder_analysis{
  
  input {
    # Required inputs
    String input_folder # gcloud storage url of the input folder containing .nd2 files
    String output_folder # gcloud storage url of the output bucket where the results will be saved
    Float pixel_size_um # pixel size in microns
    Float diameter_um # diameter of the ring tissue in microns
    Float E # Young's modulus of the gel in kPa
    Float frame_rate # frame rate of the video in frames per second
    String analysis_script # gcloud storage url of the script
    
    # Optional inputs
    Int? hardware_memory_GB
    Int? hardware_preemptible_tries 
  }

  # Working location
  String local_input_folder = "/mnt/disks/cromwell_root/data"
  
  command <<<
      mkdir -p /app/src
      mkdir ~{local_input_folder}
      mkdir ~{local_input_folder}/outputs

       # Download the analysis script from GCS
      echo "Downloading analysis script..."
      gcloud storage cp ~{analysis_script} /app/src/folder_ring_tissue_script.py

      # Get the files from the input bucket
      echo "Downloading files from Google Cloud Storage ===================="
      gcloud storage cp -r ~{input_folder}/*.nd2 ~{local_input_folder}

      echo "Directory with data ========================"
      ls -lah ~{local_input_folder}

      echo "Running analysis ========================"
      # Call the python function to analyze the ring tissue .nd2 files
      # The function will save the a folder of CSV files as the results
      python -c "
      import sys
      sys.path.append('/app/src')
      from folder_ring_tissue_script import motion_analysis
      motion_analysis(input_folder='~{local_input_folder}', output_folder='~{local_input_folder}/outputs', pixel_size_um=~{pixel_size_um}, diameter_um=~{diameter_um}, E=~{E}, frame_rate=~{frame_rate})
      "

      # Upload the converted files to the output bucket
      echo "Uploading results to Google Cloud Storage ===================="
      gcloud storage cp -r ~{local_input_folder}/outputs ~{output_folder}/
    
  >>>

  output {
    File log = stdout()
    Array[File] analyzed_movies_files = glob("~{local_input_folder}/outputs/*")
  
  }


  runtime {
    docker:"macielleah/ring_tissue:1.1"
    disks: "local-disk 50 HDD"
    memory: "${hardware_memory_GB}G"
    cpu: 4
    maxRetries: 2
    preemptible: hardware_preemptible_tries
  }

}


workflow analyze_ring_tissue_videos {
  input {

    # Required inputs
    String input_directory_gsurl # gcloud storage url of the input folder containing .nd2 files
    String output_bucket_gsurl # gcloud storage url of the output bucket where the results will be saved
    Float pixel_size_um # pixel size in microns
    Float diameter_um # diameter of the ring tissue in microns
    Float E # Young's modulus of the gel in kPa
    Float frame_rate # frame rate of the video in frames per second
    String analysis_script_gsurl
    

    # Optional inputs
    Int? hardware_memory_GB = 15
    Int? hardware_preemptible_tries = 1
  }
    call ring_tissue_folder_analysis {
      input:
        input_folder = input_directory_gsurl,
        output_folder = output_bucket_gsurl,
        pixel_size_um = pixel_size_um,
        diameter_um = diameter_um,
        E = E,
        frame_rate = frame_rate,
        analysis_script = analysis_script_gsurl,

        hardware_memory_GB = hardware_memory_GB,
        hardware_preemptible_tries = hardware_preemptible_tries
    }

   output {
     Array[File] all_analyzed_movies = ring_tissue_folder_analysis.analyzed_movies_files
  }
 
}
