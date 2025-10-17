import os
import cv2
import nd2
import numpy as np

def nd2_to_mp4(input_folder, output_folder, fps=10,):
    """
    Converts a folder of .nd2 videos to .mp4
    Saves the files in the output folder

    Args:
        input_folder (str): Path to folder with ND2 files
        output_folder (str): Path to save MP4 files
        fps (int): Frames per second for output video
        
    Returns:
        None
    """

    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True) 

    # Loop through all .nd2 files in the input folder and convert them
    for file in os.listdir(input_folder):
        if file.endswith(".nd2"):
            file_path = os.path.join(input_folder, file)
            output_path = os.path.join(output_folder, os.path.splitext(file)[0] + ".mp4")

            print(f"Processing {file_path} -> {output_path}")

            # Read .nd2 as numpy array
            data = nd2.imread(file_path) 

            n_frames, height, width = data.shape
            frame_size = (width, height)

            # Convert to mp4
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(output_path, fourcc, fps, frame_size, isColor=False)

            for i in range(n_frames):
                frame = data[i]
                # Scale to 8-bit
                if frame.dtype != np.uint8:
                    frame = cv2.convertScaleAbs(frame, alpha=(255.0 / frame.max()))

                writer.write(frame)
            writer.release()
    print("Conversion completed.")
