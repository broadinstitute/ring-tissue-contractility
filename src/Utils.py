# Imports
import os
import numpy as np
import pandas as pd
import glob



def python_aggregate_csvs_to_df(folder_path):
    """
    Aggregates all CSV files in the specified folder that match the pattern '*ExportVal_Tissues_Motion_analysis.csv' into a single Pandas DataFrame
    
    Args:
        folder_path (str): The path to the folder containing the CSV files
    
    Returns:
        pd.DataFrame: A DataFrame containing the concatenated data from all matching CSV files
    """
    csv_files = glob.glob(os.path.join(folder_path, '*ExportVal_Tissues_Motion_analysis.csv'))
    
    list_of_dfs = []

    # Loop through each CSV file found
    for file_path in csv_files:
        try:
            # Read the CSV file into a DataFrame and append it to the list
            df = pd.read_csv(file_path)
            list_of_dfs.append(df)
            print(f"Successfully loaded '{os.path.basename(file_path)}'.")
        except Exception as e:
            # Print an error message if a file fails to load
            print(f"Error loading '{file_path}': {e}")
            
    combined_df = pd.concat(list_of_dfs, ignore_index=True)

    print("\nSuccessfully aggregated all CSVs into a single DataFrame.")
    return combined_df


def aggregate_all_column_means_from_csvs(folder_path):
    """
    Aggregates the mean of all numeric columns (excluding 'time') 
    For 'time' it averages the final value (length) for each movie
   
    Args:
        folder_path (str): The path to the folder containing the CSV files
    
    Returns:
        pd.DataFrame: A DataFrame containing the mean values of all numeric columns and the final 'time' value from each CSV file
    """
    csv_files = glob.glob(os.path.join(folder_path, '*FrameByFrameResults.csv'))
    
    results = []

    # Loop through each CSV file found
    for file_path in csv_files:
        filename = os.path.basename(file_path)
        try:
            # Read the CSV file into a DataFrame
            df = pd.read_csv(file_path)
            
            # Initialize dictionary for results
            mean_values = {}

            # Calculate the mean for all columns except 'time'
            df_for_mean = df.drop(columns=['time'], errors='ignore')
            
            mean_values = df_for_mean.mean(numeric_only=True).to_dict()
            
            # Get the final value for 'time'
            if 'time' in df.columns and not df['time'].empty:
                final_time_value = df['time'].iloc[-1]
                mean_values['time'] = final_time_value 
            elif 'time' in mean_values:
                 mean_values['time'] = 0 # If there was no time value
            
            # Append the result dictionary to the list
            mean_values['filename'] = filename
            results.append(mean_values)
            print(f"Successfully calculated means and final time for '{filename}'.")

        except Exception as e:
            # Print an error message if a file fails to load
            print(f"Error loading '{file_path}': {e}")
            
    aggregated_df = pd.DataFrame(results)

    # Aggregate all the columns together
    if not aggregated_df.empty:
        cols = ['filename']
        if 'time' in aggregated_df.columns:
            cols.append('time')
        cols.extend([col for col in aggregated_df if col not in ['filename', 'time']])
        
        aggregated_df = aggregated_df[cols]

    print("\nSuccessfully aggregated mean values and final time into a single DataFrame.")
    return aggregated_df

def merge_qc_dataframes(target_df, source_df, filename_col='filename', source_key_col='Name'):
    """
    Merge together the ExportVal df and the FrameByFrame df based on matching names
    
    Args:
        target_df (pd.DataFrame): The target DataFrame to which data will be added (e.g., ExportVal DataFrame)
        source_df (pd.DataFrame): The source DataFrame from which data will be taken (e.g., FrameByFrame DataFrame)
        filename_col (str): The column in target_df that contains filenames
        source_key_col (str): The column in source_df that contains the key names to match against
    
    Returns:
        pd.DataFrame: The merged DataFrame with data from both target_df and source_df
    
    """
    # Get the name from filename
    target_key_col_name = f'{source_key_col}_KEY'
    target_df[target_key_col_name] = target_df[filename_col].str.split('_Frame').str[0]

    # Make sure we have matching names in both dfs
    if source_key_col not in source_df.columns:
        print(f"Error: Source DataFrame missing required key column ({source_key_col}). Skipping merge.")
        return target_df

    # Merge dfs together
    merged_df = pd.merge(
        target_df, 
        source_df, 
        left_on=target_key_col_name,  
        right_on=source_key_col,      
        how='left'                   
        
    )
    # Drop key column
    cols_to_drop = [target_key_col_name, f"{source_key_col}_source"]
    
    if source_key_col in merged_df.columns and source_key_col not in target_df.columns:
        cols_to_drop.append(source_key_col)

    merged_df = merged_df.drop(columns=cols_to_drop, errors='ignore')

    return merged_df


def flag_outliers_iqr(df, column):
    """
     Use IQR to identify outliers based on the specified column
     Mark them as False
     Args:
         df (pd.DataFrame): The DataFrame to analyze
         column (str): The column name to use for outlier detection
    
    Returns:
        pd.DataFrame: The DataFrame with an additional 'passed_qc' column indicating outlier status
    """
   
    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    df['passed_qc'] = df[column].between(lower_bound, upper_bound)
    
    return df

