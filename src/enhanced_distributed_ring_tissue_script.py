import os
import numpy as np
import pandas as pd
import cv2
from scipy.signal import butter, filtfilt, find_peaks
from skimage.filters import threshold_otsu
from skimage.measure import regionprops_table
import nd2
import logging
import matplotlib.pyplot as plt

def calculate_rise_fall_times(signal_series, time_series):
    """
    Calculates mean rise and fall times based on the signal (filtered_strain) using find_peaks
    Args:
        signal_series (pd.Series): The signal data (e.g., filtered_strain)
        time_series (pd.Series): The corresponding time data
    
    Returns:
        mean_rise_time (float): The mean rise time calculated from the signal
        mean_fall_time (float): The mean fall time calculated from the signal
    """
    
    rise_times = []
    fall_times = []
    
    # Drop nan values 
    valid_data = pd.DataFrame({'time': time_series, 'signal': signal_series}).dropna()
    if valid_data.empty:
        return [], np.nan, [], np.nan

    # Find peaks and valleys to identify individual contractions
    # Use distance to prevent finding multiple peaks in a single contraction
    if np.mean(np.diff(valid_data['time'])) > 0:
        min_dist_samples = int(1 / 0.1 / np.mean(np.diff(valid_data['time'])))  
    else:
        min_dist_samples = 1
       
    max_peaks, _ = find_peaks(valid_data['signal'], distance=min_dist_samples)
    min_peaks, _ = find_peaks(-valid_data['signal'], distance=min_dist_samples)
    
    # Get indices of the peaks and valleys
    max_peaks = valid_data.index[max_peaks]
    min_peaks = valid_data.index[min_peaks]

    for i in range(len(max_peaks)):
        peak_idx = max_peaks[i]
        
        # Find the preceding valley for rise time calculation
        preceding_min_indices = min_peaks[min_peaks < peak_idx]
        if not preceding_min_indices.empty:
            start_idx_rise = preceding_min_indices.max()
            rise_segment = valid_data.loc[start_idx_rise:peak_idx]
            
            # Normalize the segment from valley to peak
            min_val = rise_segment['signal'].min()
            max_val = rise_segment['signal'].max()
            
            # Calculating time it takes for the signal to rise from 10% to 90% of its peak amplitude 
            if max_val > min_val:
                normalized_signal = (rise_segment['signal'] - min_val) / (max_val - min_val)
                if np.where(normalized_signal >= 0.1)[0].size > 0:
                    rise_start_time = rise_segment['time'].iloc[np.where(normalized_signal >= 0.1)[0][0]] 
                else:
                    rise_start_time= np.nan
                if np.where(normalized_signal >= 0.9)[0].size > 0:
                    rise_end_time = rise_segment['time'].iloc[np.where(normalized_signal >= 0.9)[0][0]]  
                else:
                    rise_end_time = np.nan
                if not np.isnan(rise_start_time) and not np.isnan(rise_end_time):
                    rise_times.append(rise_end_time - rise_start_time)
        
        # Find the succeeding valley for fall time calculation
        succeeding_min_indices = min_peaks[min_peaks > peak_idx]
        if not succeeding_min_indices.empty:
            end_idx_fall = succeeding_min_indices.min()
            fall_segment = valid_data.loc[peak_idx:end_idx_fall]
            
            # Normalize the segment from peak to valley
            min_val = fall_segment['signal'].min()
            max_val = fall_segment['signal'].max()
            
            # Calculating time to fall from 90% to 10% of its peak amplitude
            if max_val > min_val:
                normalized_signal = (fall_segment['signal'] - min_val) / (max_val - min_val)
                if np.where(normalized_signal <= 0.9)[0].size > 0:
                    fall_start_time = fall_segment['time'].iloc[np.where(normalized_signal <= 0.9)[0][0]]  
                else:
                    fall_start_time = np.nan
                if np.where(normalized_signal <= 0.1)[0].size > 0:  
                    fall_end_time = fall_segment['time'].iloc[np.where(normalized_signal <= 0.1)[0][0]]  
                else:
                    fall_end_time = np.nan
                if not np.isnan(fall_start_time) and not np.isnan(fall_end_time):
                    fall_times.append(fall_end_time - fall_start_time)
                    
    # Calculate mean rise and fall times (or set to nan if no times were found)
    if rise_times:
        mean_rise_time = np.mean(rise_times)  
    else:
        mean_rise_time = np.nan
    if fall_times: 
        mean_fall_time = np.mean(fall_times) 
    else:
        mean_fall_time = np.nan

    return  mean_rise_time, mean_fall_time

def plot_tissue_coverage_mask(frame_data, outer_contour, bounding_circle_mask, centroid, name, frame_index, output_folder):
    """
    For the ring uniformity metric
    Generates and displays a plot showing the tissue and the bounding circle
    Likely don't need this for the pipeline code, but a helpful visualization
    """
    
    # Check if the inputs are valid for plotting
    if outer_contour is None or bounding_circle_mask is None:
        logging.warning(f"Skipping plot for frame {frame_index} due to missing or invalid data detected during analysis.")
        return
        
    fig, ax = plt.subplots(1, 1, figsize=(6, 6))
    
    # Convert frame to an 8-bit image for visualization (original normalized data)
    display_frame = frame_data * 255
    ax.imshow(display_frame, cmap='gray')
    
    # Plot the bounding circle mask 
    circle_overlay = np.zeros((*bounding_circle_mask.shape, 3), dtype=np.uint8)
    circle_overlay[bounding_circle_mask == 255] = [255, 100, 100] # Light red so we can see the tissue

    # Blend the overlay with the original image for transparency
    alpha = 0.3
    blended_image = display_frame[:, :, None] * (1 - alpha) + circle_overlay * alpha
    ax.imshow(blended_image.astype(np.uint8))
   
    ax.set_title(f"Tissue Coverage: {name}")
    ax.axis('off')
    
    img_name = name + '_tissue_coverage.png'
    plot_name = os.path.join(output_folder, img_name)
    plt.savefig(plot_name, bbox_inches='tight', pad_inches=0)
    logging.info(f"Tissue coverage plot generated for frame {frame_index}.")


def motion_analysis(file_path, output_folder, pixel_size_um, diameter_um, E, frame_rate, alpha, beta):
    """
    Takes in a .nd2 movies, processes it, 
    and calculates various metrics (force, stress, strain, contraction and relaxation speed, etc.)
    Saves 3 CVS files, a plot of the mask, and a runtime log in the output folder
    
    Updated to include more image enhancement and processing steps to create the mask
    
    Args:
        file_path (str): The path to the .nd2 movie file
        output_folder (str): The folder where output files will be saved
        pixel_size_um (float): The pixel size in micrometers
        diameter_um (float): The diameter of the ring tissue in micrometers
        E (float): The Young's modulus of the tissue in Pascals
        frame_rate (float): The frame rate of the movie in frames per second (default is 100)
    
    Returns:
        None
    """
    
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True) 

    # Get the filename from the path
    name = os.path.splitext(os.path.basename(file_path))[0]
    log_name = name + '_runtime_log.txt'

    # Add a runtime log
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename=os.path.join(output_folder,log_name), 
        filemode='w'         
    )

    logging.info(f"Output folder created at: {output_folder}")

    # Calculate measurements for physical units
    millimeter_per_pixel = pixel_size_um/1000  # mm / pixel
    diameter_mm = diameter_um / 1000          # um to mm
    diameter_pixel=diameter_mm/millimeter_per_pixel # theoretical diameter in pixels
    
    # Process the single .nd2 file
    logging.info(f"Analyzing video: {file_path}")

    # Read the movie and get dimensions
    try:
        nd2_file = nd2.imread(file_path) 
    except Exception as e:
        logging.error(f"Could not read ND2 file {file_path}: {e}")
        return

    if nd2_file.ndim == 4:
        # This is a 4D array (T, C, H, W). Select the first channel (index 0)
        movie_data = nd2_file[:, :, :, 0]
        logging.info(f"Video detected as 3-channel (4D array), using first channel (index 0).")
    elif nd2_file.ndim == 3:
        # This is a 3D array (T, H, W) - a single channel movie
        movie_data = nd2_file
        logging.info(f"Video detected as single-channel (3D array).")
    else:
        logging.error(f"Unexpected ND2 file shape: {nd2_file.shape}. Skipping file.")
        return

    n = movie_data.shape[0]  # Number of frames
    h = movie_data.shape[1]  # Height
    w = movie_data.shape[2]  # Width
    
    delta_T = 1/frame_rate

    # Array to hold the frames
    video_frames = np.zeros((h, w, n), dtype=np.float32)

    # Read all frames and convert to a float array
    for i in range(n):
        frame = movie_data[i, :, :]  
        
        # Normalize and ensure frame is not entirely zero before division
        max_val = np.max(frame)
        if max_val > 0:
            video_frames[:, :, i] = frame / max_val
        else:
            video_frames[:, :, i] = frame # Keep as zero if max is zero


    # Automatically find the optimal threshold using a representative image
    rep_frame_index = min(9, n - 1) # using frame 9 (or n-1 if less than 9 frame), but theoretically could be any frame
    
    # Convert to 8bit
    frame_8bit_for_thresh = np.uint8(video_frames[:, :, rep_frame_index] * 255)
    
    # Apply Gaussian Blur to remove noise before thresholding
    morph_kernel = np.ones((7, 7), np.uint8) 
    gaussian_kernel_size = 5
    processed_frame_8bit_for_thresh = cv2.GaussianBlur(frame_8bit_for_thresh, (gaussian_kernel_size, gaussian_kernel_size), 0)

    # Otsu threshold the image
    bw_threshold = threshold_otsu(processed_frame_8bit_for_thresh)
    bw_sensitivity = bw_threshold / 255.0 # To match the value inputed into MATLAB

    # Initialize arrays for storing data
    area_frames = np.zeros(n)
    minor_length_frames = np.zeros(n)
    major_length_frames = np.zeros(n)
    coverage_frames = np.zeros(n)
    max_radius_frames = np.zeros(n)
    tissue_mask_area_pixels = np.zeros(n)

    plot_data = {
                'frame_data': None,
                'outer_contour': None,
                'bounding_circle_mask': None,
                'centroid': (0, 0)
            }

    # Loop through to do thresholding and find the area of the inner ring
    for i in range(video_frames.shape[2]):
        frame = video_frames[:, :, i]

        # Apply the same preprocessing step to the current frame before thresholding
        frame_8bit = np.uint8(frame * 255)


        enhanced_frame = cv2.convertScaleAbs(frame_8bit, alpha=alpha, beta=beta)

        # Apply Gaussian blur for noise reduction
        processed_frame_8bit = cv2.GaussianBlur(enhanced_frame, (gaussian_kernel_size, gaussian_kernel_size), 0)

        # Save a plot of the first mask for reference
        if i == 0:   
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.imshow(processed_frame_8bit, cmap='gray')
            ax.set_title(f"Enhanced : {name}")
            ax.axis('off')

            img_name = name + '_enhanced.png'
            plot_name = os.path.join(output_folder, img_name)
            plt.savefig(plot_name, bbox_inches='tight', pad_inches=0)


        # Threshold the image using the threshold determined above
        _, bw = cv2.threshold(processed_frame_8bit, bw_threshold, 255, cv2.THRESH_BINARY_INV)

        bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, morph_kernel, iterations=10)

        bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, morph_kernel, iterations=1)


        # Save a plot of the first mask for reference
        if i == 0:   
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.imshow(bw, cmap='gray')
            ax.set_title(f"Mask: {name}")
            ax.axis('off')

            mask_name = name + '_mask.png'
            plot_name = os.path.join(output_folder, mask_name)
            plt.savefig(plot_name, bbox_inches='tight', pad_inches=0)


        # Find all contours and their hierarchy
        contours, _ = cv2.findContours(bw, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        # Get the inner hole
        if len(contours) >= 2:
            sorted_contours = sorted(contours, key=cv2.contourArea, reverse=True)
            inner_ring_contour = sorted_contours[1] # The second largest contour is likely the inner hole/tissue

            # Draw a mask of just this inner hole/tissue to get properties
            mask = np.zeros_like(bw)

            cv2.drawContours(mask, [inner_ring_contour], -1, 255, -1)

            if i == 0: 
                fig, ax = plt.subplots(figsize=(8, 8))
                ax.imshow(mask, cmap='gray')
                ax.set_title(f"Inner Ring Mask: {name}")
                ax.axis('off')

                img_name = name + '_inner_ring.png'
                plot_name = os.path.join(output_folder, img_name)
                plt.savefig(plot_name, bbox_inches='tight', pad_inches=0)


            # Use regionprops_table on the inner ring mask to get the properties
            props = regionprops_table(mask, properties=['area', 'major_axis_length', 'minor_axis_length', 'eccentricity', 'centroid'])
            stats = pd.DataFrame(props)

            # Store the inner ring measurements 
            if not stats.empty:
                stats.rename(columns={'centroid-0': 'centroid-y', 'centroid-1': 'centroid-x'}, inplace=True)
                diameters = (stats['major_axis_length'] + stats['minor_axis_length']) / 2

                # Apply filters for valid ring detection
                valid_stats = stats[
                    (stats['eccentricity'] <= 0.6) & 
                    (diameters >= 0.75 * diameter_pixel) &
                    (diameters <= 1.5 * diameter_pixel)
                ]

                if not valid_stats.empty:
                    t_new = valid_stats.iloc[0]
                    area_frames[i] = t_new['area']
                    minor_length_frames[i] = t_new['minor_axis_length']
                    major_length_frames[i] = t_new['major_axis_length']
                else:
                    area_frames[i], minor_length_frames[i], major_length_frames[i] = np.nan, np.nan, np.nan
            else:
                area_frames[i], minor_length_frames[i], major_length_frames[i] = np.nan, np.nan, np.nan


            # Find all contours and their hierarchy
            contours, _ = cv2.findContours(bw, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            sorted_contours = sorted(contours, key=cv2.contourArea, reverse=True)

            # Take the first contour as the outer tissue contour
            outer_tissue_contour = sorted_contours[0] 

            # Calculate centroid of the entire tissue structure
            M = cv2.moments(outer_tissue_contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
            else:
                # Fallback: cannot find centroid
                logging.warning(f"Contour moments zero for frame {i}. Skipping coverage calculation.")
                coverage_frames[i], max_radius_frames[i] = np.nan, np.nan
                continue

            # Find maximum radius (R_max) from the centroid to the contour
            R_max = 0
            for point in outer_tissue_contour:
                x, y = point[0]
                distance = np.sqrt((x - cx)**2 + (y - cy)**2)
                if distance > R_max:
                    R_max = distance

            # Create the bounding circle mask
            R_max_int = int(R_max) + 1 # Add small buffer for robustness
            bounding_circle_mask = np.zeros_like(bw)
            cv2.circle(bounding_circle_mask, (cx, cy), R_max_int, 255, -1) # Draw solid circle

            # Create the tissue mask- area enclosed by the outermost contour (sorted_contours[1])
            tissue_mask = np.zeros_like(bw)
            cv2.drawContours(tissue_mask, [outer_tissue_contour], -1, 255, -1)
            tissue_mask_pixels = np.sum(tissue_mask == 255)

            # Calculate intersection and metric
            intersection_mask = cv2.bitwise_and(tissue_mask, bounding_circle_mask)

            total_area_pixels = np.sum(bounding_circle_mask == 255)
            tissue_area_pixels = np.sum(intersection_mask == 255)

            if total_area_pixels > 0:
                coverage_metric = tissue_area_pixels / total_area_pixels
            else:
                coverage_frames[i], max_radius_frames[i], tissue_mask_area_pixels[i] = np.nan, np.nan, np.nan

            # Store metric
            coverage_frames[i] = coverage_metric
            max_radius_frames[i] = R_max
            tissue_mask_area_pixels[i] = tissue_mask_pixels
            

            # Store plot data if this frame was selected for visualization
            if i == 0:
                plot_data['frame_data'] = frame
                plot_data['outer_contour'] = outer_tissue_contour
                plot_data['bounding_circle_mask'] = bounding_circle_mask
                plot_data['centroid'] = (cx, cy)

                plot_tissue_coverage_mask(
                    plot_data['frame_data'],
                    plot_data['outer_contour'],
                    plot_data['bounding_circle_mask'],
                    plot_data['centroid'],
                    name,
                    0,
                    output_folder 
                )

        # Handle case where not enough contours were found
        else:
            area_frames[i], minor_length_frames[i], major_length_frames[i] = np.nan, np.nan, np.nan
            coverage_frames[i], max_radius_frames[i], tissue_mask_area_pixels[i] = np.nan, np.nan, np.nan


    # Store all the collected data in a DataFrame
    raw_data = pd.DataFrame({
        'time': np.arange(n) * delta_T,
        'area_frames': area_frames,
        'minor_length_frames': minor_length_frames,
        'major_length_frames': major_length_frames,
        'coverage_metric': coverage_metric,
        'tissue_mask_area_pixels': tissue_mask_area_pixels
    })

    # Clean up the raw data
    raw_data.replace([np.inf, -np.inf], np.nan, inplace=True)
    raw_data.interpolate(method='linear', inplace=True)

    # Butterworth filter
    fs = 1/ delta_T
    fc = 5  # Cut-off frequency
    b, a = butter(2, fc / fs, 'low')
    filtered_area = filtfilt(b, a, raw_data['area_frames'].values)

    raw_data['filtered_area'] = filtered_area

    # Calculate strain
    max_area = np.max(filtered_area)
    contraction = -(filtered_area - max_area)
    filtered_strain = -(filtered_area - max_area) / max_area

    raw_data['contraction'] = contraction
    raw_data['filtered_strain'] = filtered_strain


    # Frequency with fft
    Y = np.fft.fft(filtered_strain)
    L = len(filtered_strain)

    fftfreq = fs * np.arange(L // 2 + 1) / L 
    P2 = np.abs(Y / L)
    P1 = P2[:L // 2 + 1]
    P1[1:-1] = 2 * P1[1:-1]

    # Find the frequency with the maximum amplitude
    fftpeaks, _ = find_peaks(P1)
    freq_from_fft = 0

    # Add error handling
    if len(fftpeaks) > 0:
        max_peak_index = np.argmax(P1[fftpeaks])
        freq_from_fft = fftfreq[fftpeaks[max_peak_index]]
        MP = 1/freq_from_fft/2 * frame_rate
    else:
        freq_from_fft = 0  # Handle case with no peaks
        MP = 0
        logging.warning("No peaks found after fft")
        max_peak_indices = []
        min_peak_indices = []

    raw_data['contraction_freq_from_FFT'] = freq_from_fft

    # Contraction characterization using peaks
    if not np.isnan(freq_from_fft) and freq_from_fft > 0:
        MH = 0.6 * raw_data['contraction'].max()

        # Find peaks and valleys in the contraction data
        max_peak_indices, _ = find_peaks(raw_data['contraction'], height=MH, distance=MP)
        min_peak_indices, _ = find_peaks(-raw_data['contraction'], distance=MP)

        raw_data['contract_max_strain'] = [[] for _ in range(len(raw_data))]
        raw_data.at[0, 'contract_max_strain'] = raw_data['filtered_strain'][max_peak_indices].tolist()
        raw_data['mean_contract_max_strain'] = raw_data['contract_max_strain'].apply(lambda x: np.mean(x) if x else np.nan)

        raw_data['contract_min_strain'] = [[] for _ in range(len(raw_data))]
        raw_data['mean_contract_min_strain'] = np.nan

        # Find the closest valley after each peak
        if len(max_peak_indices) > 1 and len(min_peak_indices) > 0:
            valid_minima_indices = []
            for max_idx in max_peak_indices:
                # Find all minima indices that occur after the current maxima index
                indices_after_peak = min_peak_indices[min_peak_indices > max_idx]
                if len(indices_after_peak) > 0:
                    # Append the first one found
                    valid_minima_indices.append(indices_after_peak[0])

            # Remove duplicate indices
            unique_minima_indices = np.unique(valid_minima_indices)

            if len(unique_minima_indices) > 0:
                raw_data.at[0, 'contract_min_strain'] = raw_data['filtered_strain'][unique_minima_indices].tolist()
                raw_data['mean_contract_min_strain'] = raw_data['contract_min_strain'].apply(lambda x: np.mean(x) if x else np.nan)

    else:
        raw_data['contract_max_strain'] = [[] for _ in range(len(raw_data))]
        raw_data['contract_min_strain'] = [[] for _ in range(len(raw_data))]
        raw_data['mean_contract_max_strain'] = np.nan
        raw_data['mean_contract_min_strain'] = np.nan
        freq_from_fft = np.nan

    # Rise and fall times
    if not raw_data['filtered_strain'].dropna().empty:
        mean_rise_time, mean_fall_time = calculate_rise_fall_times(
            raw_data['filtered_strain'], raw_data['time']
        )
    else:
        mean_rise_time, mean_fall_time = np.nan, np.nan
        logging.warning("Filterd_strain is empty or all NaN, cannot calculate rise/fall times")

    raw_data['mean_rise_time'] = mean_rise_time
    raw_data['mean_fall_time'] = mean_fall_time



    # Measurement calculations:

    # Stress (Pa) = E * strain
    stress_pa = E * raw_data['filtered_strain']

    # Convert Pa to mN/mm^2
    stress_mNmm2 = stress_pa * 0.001

    # Area (mm^2) = Area (pixels) * (mm/pixel)^2
    area_mm2 = raw_data['filtered_area'] * (millimeter_per_pixel ** 2)
    tissue_mask_area_mm2 = raw_data['tissue_mask_area_pixels'] * (millimeter_per_pixel ** 2)

    # Force (mN) = Stress (mN/mm^2) * Area (mm^2)
    force_mN = stress_mNmm2 * area_mm2

    # Convert Force to nN
    force_nN = force_mN * 1e6

    # Add results
    raw_data['stress_mNmm2'] = stress_mNmm2
    raw_data['area_mm2'] = area_mm2
    raw_data['force_nN'] = force_nN
    raw_data['tissue_mask_area_mm2'] = tissue_mask_area_mm2


    # Calculate cycle level metrics     
    cycle_results_dict = {
        'amplitude_strain': [], 
        'contract_time': [], 
        'contract_speed_strain': [], 
        'relax_time': [], 
        'relax_speed_strain': [], 
        'rest_time': []}

    if not raw_data['filtered_strain'].dropna().empty and not np.isnan(freq_from_fft):
        MH = 0.6 * raw_data['contraction'].max()

        max_peak_indices, _ = find_peaks(raw_data['contraction'], height=MH, distance=MP)
        min_peak_indices, _ = find_peaks(-raw_data['contraction'], distance=MP)

        # About contraction
        for j in range(min(len(min_peak_indices), len(max_peak_indices) - 1)):
            amplitude = raw_data['filtered_strain'].iloc[max_peak_indices[j+1]] - raw_data['filtered_strain'].iloc[min_peak_indices[j]]
            time_beg = raw_data['time'].iloc[min_peak_indices[j]]
            time_end = raw_data['time'].iloc[max_peak_indices[j+1]]
            contraction_time = time_end - time_beg

            cycle_results_dict['amplitude_strain'].append(amplitude)
            cycle_results_dict['contract_time'].append(contraction_time)
            cycle_results_dict['contract_speed_strain'].append(amplitude / contraction_time)

        # About relaxation
        for j in range(len(max_peak_indices)):
            # Find the next valley after the current peak
            next_min_idx = min_peak_indices[min_peak_indices > max_peak_indices[j]]
            if len(next_min_idx) == 0:
                continue

            rel90_val = (raw_data['filtered_strain'].iloc[max_peak_indices[j]] - raw_data['filtered_strain'].iloc[next_min_idx[0]]) * 0.1 + raw_data['filtered_strain'].iloc[next_min_idx[0]]

            # Find the time point where the strain reaches 90% of its relaxation
            relaxation_segment = raw_data.loc[max_peak_indices[j]:next_min_idx[0]]
            closest_idx = np.abs(relaxation_segment['filtered_strain'] - rel90_val).idxmin()

            relax_time = raw_data['time'].iloc[closest_idx] - raw_data['time'].iloc[max_peak_indices[j]]
            relax_speed = (raw_data['filtered_strain'].iloc[max_peak_indices[j]] - rel90_val) / relax_time
            rest_time = raw_data['time'].iloc[next_min_idx[0]] - raw_data['time'].iloc[closest_idx]

            cycle_results_dict['relax_time'].append(relax_time)
            cycle_results_dict['relax_speed_strain'].append(relax_speed)
            cycle_results_dict['rest_time'].append(rest_time)

    # Convert the dictionary to a DataFrame
    cycle_results = pd.DataFrame(dict([ (k, pd.Series(v)) for k, v in cycle_results_dict.items() ]))

    # Calculate contraction/relaxation speed (velocity)
    raw_data['loc_speed_strain'] = np.gradient(raw_data['filtered_strain'], raw_data['time'])

    # Butterworth filter
    #delta = np.mean(np.diff(raw_data['time']))
    #fs = 1 / delta
    #fc = 20  # Filter lowpass 20Hz

    #b, a = butter(2, fc /fs, 'low', analog=False)
    #raw_data['filtered_loc_speed'] = filtfilt(b, a, raw_data['loc_speed_strain'].values)
    raw_data['filtered_loc_speed'] = raw_data['loc_speed_strain']

    # Only proceed if there is enough data points for find_peaks and a valid MP
    if len(raw_data['filtered_loc_speed']) > MP and MP > 0:
        mh = np.nanmax(raw_data['filtered_loc_speed'].iloc[10:-1]) / 3
        mh2 = np.nanmax(-raw_data['filtered_loc_speed'].iloc[10:-1]) / 3

        # find_peaks returns a tuple --> first element is the array of peak locations
        loc_max, pk_max_props = find_peaks(raw_data['filtered_loc_speed'], distance=MP, height=mh)
        pkmax = pk_max_props['peak_heights']

        # Store results
        raw_data['max_contract_speed_strain'] = np.nan
        raw_data.loc[loc_max, 'max_contract_speed_strain'] = pkmax
        raw_data['max_contract_speed_strain'] = np.mean(pkmax) if len(pkmax) > 0 else np.nan

        # find_peaks for relaxation speed using valleys
        loc_min, pk_min_props = find_peaks(-raw_data['filtered_loc_speed'], distance=MP, height=mh2)
        pkmin = pk_min_props['peak_heights']

        # Store results
        raw_data['max_relax_speed_strain'] = np.nan
        raw_data.loc[loc_min, 'max_relax_speed_strain'] = pkmin
        raw_data['max_relax_speed_strain'] = np.mean(pkmin) if len(pkmin) > 0 else np.nan

    else:
        # Handle the case where there is not enough data or MP is invalid
        raw_data['max_contract_speed_strain'] = np.nan
        raw_data['max_relax_speed_strain'] = np.nan


    # Create a dictionary for summary results
    export_val = {
        'Name': name,
        'frame_rate': frame_rate, 
        'num_frames': n, 
        'pixel_size_um': pixel_size_um, 
        'diameter_mm': diameter_mm, 
        'bw_sensitivity': bw_sensitivity,
        'Duration': raw_data['time'].max(),
        'Height': h,
        'Width': w,
        'CoverageMetric': coverage_metric,
        'ContractionFreqFromFFT': freq_from_fft,
        'MeanAmpliStrain': cycle_results['amplitude_strain'].mean(),
        'MeanRiseTimeStrain': raw_data['mean_rise_time'].mean(),  
        'MeanFallTimeStrain': raw_data['mean_fall_time'].mean(), 
        'MeanContractTime': cycle_results['contract_time'].mean(),
        'MeanContractSpeedStrain': cycle_results['contract_speed_strain'].mean(),
        'MeanRelaxTime': cycle_results['relax_time'].mean(),
        'MeanRelaxSpeedStrain': cycle_results['relax_speed_strain'].mean(),
        'MeanRestTime': cycle_results['rest_time'].mean(),
        'MeanRestTimeStd': cycle_results['rest_time'].std(),
        'MeanMaxContractSpeedStrain': raw_data['max_contract_speed_strain'].mean() if 'max_contract_speed_strain' in raw_data else np.nan,
        'MeanMaxRelaxSpeedStrain': raw_data['max_relax_speed_strain'].mean() if 'max_relax_speed_strain' in raw_data else np.nan,
        'StdTimeBtwMax': np.std(np.diff(raw_data['time'].iloc[max_peak_indices])) if len(max_peak_indices) > 1 else np.nan,
        'MeanContractMaxStrain': raw_data['mean_contract_max_strain'].mean(),
        'MeanContractMinStrain': raw_data['mean_contract_min_strain'].mean() 
    }
    raw_data_cleaned= raw_data.drop(['mean_rise_time','mean_fall_time','mean_contract_max_strain', 'mean_contract_min_strain', 'contraction_freq_from_FFT','mean_contract_min_strain','contract_max_strain', 'contract_min_strain','max_contract_speed_strain','max_relax_speed_strain', 'coverage_metric'], axis=1)

    # Create a df from the export_val dictionary
    export_val_df = pd.DataFrame([export_val])

    # Define file paths
    frame_filename = os.path.join(output_folder, f'{name}_FrameByFrameResults.csv')
    cycle_filename = os.path.join(output_folder, f'{name}_cycles.csv')
    single_metrics_filename = os.path.join(output_folder, f'{name}_ExportVal_Tissues_Motion_analysis.csv')

    # Save dfs
    raw_data_cleaned.to_csv(frame_filename, index=False)
    cycle_results.to_csv(cycle_filename, index=False)
    export_val_df.to_csv(single_metrics_filename, index=False)

    logging.info(f"Frame-level data saved to: {frame_filename}")
    logging.info(f"Cycle-level data saved to: {cycle_filename}")
    logging.info(f"Summary data saved to: {single_metrics_filename}")

    logging.info(f"Analysis complete for {name}")