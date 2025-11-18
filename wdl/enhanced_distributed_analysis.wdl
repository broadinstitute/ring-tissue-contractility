version 1.0

## Copyright Broad Institute, 2021
##
## LICENSING :
## This script is released under the WDL source code license (BSD-3)
## (see LICENSE in https://github.com/openwdl/wdl).

task gcloud_storage_ls {

  input {
    String directory_gsurl  # Input directory gsURL
    String file_extension = ".nd2"
  }

  command {
    # List all files in the input directory with the specified extension
    gcloud storage ls ~{directory_gsurl}/** | grep ~{file_extension}
  }
  
  output {
    Array[String] file_array = read_lines(stdout())
  }

  runtime {
    docker: "gcr.io/google.com/cloudsdktool/google-cloud-cli:alpine"
    disks: "local-disk 50 HDD"
    memory: "15G"
    cpu: 4
    maxRetries: 2
    preemptible: 2
  }
}

task single_ring_tissue_analysis{
  
  input {
    # Required inputs
    File video_file # gcloud storage url of the movie file to be analyzed
    String output_folder # gcloud storage url of the output bucket where the results will be saved
    Float pixel_size_um # pixel size in microns
    Float diameter_um # diameter of the ring tissue in microns
    Float E # Young's modulus of the gel in Pa
    Float frame_rate # frame rate of the video in frames per second
    
    # Optional inputs
    Int? hardware_memory_GB
    Int? hardware_preemptible_tries 
  }

  # Working location  
  String local_output_folder = "outputs"
  
  command <<<
      mkdir -p /app/src
      mkdir ~{local_output_folder}

     
      echo "Running analysis on ~{video_file} ========================"
      # Call the python function to analyze the ring tissue .nd2 file
      python -c "
      import sys
      sys.path.append('/app/src')
      from enhanced_distributed_ring_tissue_script import motion_analysis
      motion_analysis(file_path='~{video_file}', output_folder='~{local_output_folder}', pixel_size_um=~{pixel_size_um}, diameter_um=~{diameter_um}, E=~{E}, frame_rate=~{frame_rate})
      "

      # Upload the converted files to the output bucket
      echo "Uploading results to Google Cloud Storage ===================="
      gcloud storage cp -r ~{local_output_folder} ~{output_folder}/
    
  >>>

  output {
   Array[File] analyzed_files = glob("~{local_output_folder}/*")
  
  }

  runtime {
    docker:"macielleah/ring_tissue:1.4"
    disks: "local-disk 50 HDD"
    memory: "${hardware_memory_GB}G"
    cpu: 4
    maxRetries: 2
    preemptible: hardware_preemptible_tries
  }

}


workflow distributed_analyze_ring_tissue_videos {
  input {
    # Required inputs
    String input_directory_gsurl # gcloud storage url of the input folder containing .nd2 files
    String output_bucket_gsurl # gcloud storage url of the output bucket where the results will be saved
    Float pixel_size_um # pixel size in microns
    Float diameter_um # diameter of the ring tissue in microns
    Float E # Young's modulus of the gel in Pa
    Float frame_rate # frame rate of the video in frames per second

    # Optional inputs
    Int? hardware_memory_GB = 15
    Int? hardware_preemptible_tries = 1
  }

  call gcloud_storage_ls as ls {
    input:
      directory_gsurl = input_directory_gsurl
  }

  # scatter ls.file_array
  scatter (video_file in ls.file_array){
    call single_ring_tissue_analysis {
      input:
        video_file = video_file,
        output_folder = output_bucket_gsurl,
        pixel_size_um = pixel_size_um,
        diameter_um = diameter_um,
        E = E,
        frame_rate = frame_rate,
        hardware_memory_GB = hardware_memory_GB,
        hardware_preemptible_tries = hardware_preemptible_tries
        }
    }

   output {
     Array[File] all_analyzed_movies = flatten(single_ring_tissue_analysis.analyzed_files)
    
    }

}
