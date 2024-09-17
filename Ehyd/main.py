# IMPORTS
import pandas as pd
import numpy as np
import matplotlib
import warnings
import pickle
import os
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from datetime import datetime
from scipy.spatial import distance
from statsmodels.tsa.statespace.sarimax import SARIMAX
import matplotlib.pyplot as plt
# matplotlib.use('Qt5Agg')
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.float_format', lambda x: '%.3f' % x)
pd.set_option('display.max_colwidth', None)
pd.set_option('display.width', 500)
warnings.simplefilter('ignore', category=ConvergenceWarning)


# FUNCTIONS
def station_coordinates(input):
    """
    Creates a dataset consisting of measurement station IDs and their corresponding X and Y coordinates.

    Args:
        input: Directory of the measurement station CSV file.

    Returns:
        df: A DataFrame containing columns "x", "y", and "hzbnr01".
    """
    df = pd.read_csv(os.path.join("Ehyd", "datasets_ehyd", input, "messstellen_alle.csv"), sep=";")
    output_df = df[["x", "y", "hzbnr01"]].copy()
    output_df['x'] = output_df['x'].astype(str).str.replace(',', '.').astype("float32")
    output_df['y'] = output_df['y'].astype(str).str.replace(',', '.').astype("float32")
    return output_df

def to_dataframe(folder_path, tip_coordinates):
    """
    Processes CSV files in the specified folder, skipping header information and creating DataFrames
    from the section marked by "Werte". Converts "L�cke" (Gap) values to NaN and skips rows with
    invalid data or specific keywords.

    For each CSV file, it extracts data starting after the "Werte:" line, processes date and value
    columns, and stores each DataFrame in a dictionary where the key is derived from the filename.
    Additionally, it matches IDs with tip coordinates and returns a DataFrame containing matched coordinates.

    Args:
        folder_path (str): The directory path where the CSV files are located.
        tip_coordinates (pd.DataFrame): A DataFrame containing coordinates to be matched with the IDs.

    Returns:
        dict: A dictionary where keys are IDs (extracted from filenames) and values are DataFrames.
        pd.DataFrame: A DataFrame with matched coordinates based on IDs.
    """
    dataframes_dict = {}
    coordinates = pd.DataFrame()

    for filename in os.listdir(folder_path):
        try:
            if filename.endswith(".csv"):
                filepath = os.path.join(folder_path, filename)

                with open(filepath, 'r', encoding='latin1') as file:
                    lines = file.readlines()

                    # Find the starting index of the data section
                    start_idx = next((i for i, line in enumerate(lines) if line.startswith("Werte:")), None)
                    if start_idx is None:
                        continue  # Skip files that do not contain 'Werte:'

                    start_idx += 1
                    header_line = lines[start_idx - 1].strip()

                    # Skip files with 'Invalid' in the header line
                    if "Invalid" in header_line:
                        continue

                    data_lines = lines[start_idx:]

                    data = []
                    for line in data_lines:
                        if line.strip():  # Skip empty lines
                            try:
                                date_str, value_str = line.split(';')[:2]

                                # Try multiple date formats
                                try:
                                    date = datetime.strptime(date_str.strip(), "%d.%m.%Y %H:%M:%S").date()
                                except ValueError:
                                    try:
                                        date = datetime.strptime(date_str.strip(), "%d.%m.%Y %H:%M").date()
                                    except ValueError:
                                        continue

                                # Skip rows with invalid data or specific keywords
                                if any(keyword in value_str for keyword in ["F", "K", "rekonstruiert aus Version 3->"]):
                                    continue

                                # Convert value to float
                                try:
                                    value = np.float32(value_str.replace(',', '.'))
                                except ValueError:
                                    value = np.nan  # Assign NaN if conversion fails

                                data.append([date, value])

                            except Exception:
                                break

                    if data:  # Create DataFrame only if data exists
                        df = pd.DataFrame(data, columns=['Date', 'Values'])
                        df.drop(df.index[-1], inplace=True)  # Dropping the last row (2022-01-01)
                        df_name = f"{filename[-10:-4]}"

                        dataframes_dict[df_name] = df

                        # Convert keys to integers
                        int_keys = [int(key) for key in dataframes_dict.keys() if key.isdigit()]
                        coordinates = tip_coordinates[tip_coordinates['hzbnr01'].isin(int_keys)]

        except Exception:
            continue

    return dataframes_dict, coordinates

def to_global(dataframes_dict, prefix=''):
    """
    Adds DataFrames from a dictionary to the global namespace with optional prefix.

    Args:
        dataframes_dict (dict): A dictionary where keys are names (str) and values are DataFrames.
        prefix (str): An optional string to prefix to each DataFrame name in the global namespace.
    """
    for name, dataframe in dataframes_dict.items():
        globals()[f"{prefix}{name}"] = dataframe

def process_dataframes(df_dict):
    """
    Processes a dictionary of DataFrames by converting date columns, resampling daily data to monthly, and reindexing.

    Args:
        df_dict (dict): A dictionary where keys are DataFrame names and values are DataFrames.

    Returns:
        dict: The processed dictionary of DataFrames with date conversion, resampling, and reindexing applied.
    """
    for df_name, df_value in df_dict.items():
        df_value['Date'] = pd.to_datetime(df_value['Date'])

        if df_value['Date'].dt.to_period('D').nunique() > df_value['Date'].dt.to_period('M').nunique():
            df_value.set_index('Date', inplace=True)
            df_dict[df_name] = df_value.resample('MS').mean()

        else:
            df_value.set_index('Date', inplace=True)
            df_dict[df_name] = df_value

        all_dates = pd.date_range(start='1960-01-01', end='2021-12-01', freq='MS')
        new_df = pd.DataFrame(index=all_dates)
        df_dict[df_name] = new_df.join(df_dict[df_name], how='left').fillna("NaN")

    return df_dict

def process_and_store_data(folder, coordinates, prefix, station_list=None):
    data_dict, data_coordinates = to_dataframe(folder, coordinates)
    data_dict = process_dataframes(data_dict)

    for df_name, df in data_dict.items():
        df.astype('float32')

    to_global(data_dict, prefix=prefix)

    if station_list:
        data_dict = filter_dataframes_by_stations(data_dict, station_list)
        data_coordinates = data_coordinates[data_coordinates['hzbnr01'].astype(str).isin(station_list)]

    return data_dict, data_coordinates

def filter_dataframes_by_stations(dataframes_dict, station_list):
    """
    Filters a dictionary of DataFrames to include only those whose names are specified in a given CSV file.

    Args:
        dataframes_dict (dict): A dictionary where keys are names (str) and values are DataFrames.
        station_list (str): Path to a CSV file that contains the names (str) of the DataFrames to filter.

    Returns:
        dict: A filtered dictionary containing only the DataFrames whose names are listed in the CSV file.
    """
    filtered_dict = {name: df for name, df in dataframes_dict.items() if name in station_list}
    return filtered_dict

def save_to_pickle(item, filename):
    """
    Saves a dictionary to a pickle file.

    Args:
        data_dict (dict): The dictionary to save.
        filename (str): The path to the output pickle file.
    """
    with open(filename, 'wb') as f:
        pickle.dump(item, f)

########################################################################################################################
# Creating Dataframes from given CSVs
########################################################################################################################

# Define paths and coordinates
groundwater_all_coordinates = station_coordinates("Groundwater")
precipitation_coordinates = station_coordinates("Precipitation")
sources_coordinates = station_coordinates("Sources")
surface_water_coordinates = station_coordinates("Surface_Water")

# Precipitation: Rain and Snow
precipitation_folders = [
    ("N-Tagessummen", "rain_"),
    ("NS-Tagessummen", "snow_")]

source_folders = [
    ("Quellsch�ttung-Tagesmittel", "source_fr_"),
    ("Quellleitf�higkeit-Tagesmittel", "conductivity_"),
    ("Quellwassertemperatur-Tagesmittel", "source_temp_")]

surface_water_folders = [
    ("W-Tagesmittel", "surface_water_level_"),
    ("WT-Monatsmittel", "surface_water_temp_"),
    ("Schwebstoff-Tagesfracht", "sediment_"),
    ("Q-Tagesmittel", "surface_water_fr_")]

# Groundwater Dictionary (Filtered down to the requested 487 stations)
stations = pd.read_csv(os.path.join("Ehyd", "datasets_ehyd", "gw_test_empty.csv"))
station_list = [col for col in stations.columns[1:]]
filtered_groundwater_dict, filtered_gw_coordinates = process_and_store_data(
    os.path.join("Ehyd", "datasets_ehyd", "Groundwater", "Grundwasserstand-Monatsmittel"),
    groundwater_all_coordinates, "gw_", station_list)

gw_temp_dict, gw_temp_coordinates = process_and_store_data(os.path.join("Ehyd", "datasets_ehyd", "Groundwater", "Grundwassertemperatur-Monatsmittel"), groundwater_all_coordinates, "gwt_")
rain_dict, rain_coord = process_and_store_data(os.path.join("Ehyd", "datasets_ehyd", "Precipitation", precipitation_folders[0][0]), precipitation_coordinates, "rain_")
snow_dict, snow_coord = process_and_store_data(os.path.join("Ehyd", "datasets_ehyd", "Precipitation", precipitation_folders[1][0]), precipitation_coordinates, "snow_")
source_fr_dict, source_fr_coord = process_and_store_data(os.path.join("Ehyd", "datasets_ehyd", "Sources", source_folders[0][0]), sources_coordinates, "source_fr_")
conduct_dict, conduct_coord = process_and_store_data(os.path.join("Ehyd", "datasets_ehyd", "Sources", source_folders[1][0]), sources_coordinates, "conduct_")
source_temp_dict, source_temp_coord = process_and_store_data(os.path.join("Ehyd", "datasets_ehyd", "Sources", source_folders[2][0]), sources_coordinates, "source_temp_")
surface_water_lvl_dict, surface_water_lvl_coord = process_and_store_data(os.path.join("Ehyd", "datasets_ehyd", "Surface_Water", surface_water_folders[0][0]), surface_water_coordinates, "surface_water_lvl_")
surface_water_temp_dict, surface_water_temp_coord = process_and_store_data(os.path.join("Ehyd", "datasets_ehyd", "Surface_Water", surface_water_folders[1][0]), surface_water_coordinates, "surface_water_temp_")
sediment_dict, sediment_coord = process_and_store_data(os.path.join("Ehyd", "datasets_ehyd", "Surface_Water", surface_water_folders[2][0]), surface_water_coordinates, "sediment_")
surface_water_fr_dict, surface_water_fr_coord = process_and_store_data(os.path.join("Ehyd", "datasets_ehyd", "Surface_Water", surface_water_folders[3][0]), surface_water_coordinates, "surface_water_fr_")

########################################################################################################################
# Gathering associated additional features for required 487 stations
########################################################################################################################
def calculate_distance(coord1, coord2):
    """
    Calculates the Euclidean distance between two points in a Cartesian coordinate system.

    Args:
        coord1 (tuple): A tuple representing the coordinates (x, y) of the first point.
        coord2 (tuple): A tuple representing the coordinates (x, y) of the second point.

    Returns:
        float: The Euclidean distance between the two points.
    """
    return distance.euclidean(coord1, coord2)

def find_nearest_coordinates(gw_row, df, k=20):
    """
    Finds the `k` nearest coordinates from a DataFrame to a given point.

    Args:
        gw_row (pd.Series): A pandas Series representing the coordinates (x, y) of the given point.
        df (pd.DataFrame): A DataFrame containing the coordinates with columns "x" and "y".
        k (int, optional): The number of nearest coordinates to return. Defaults to 20.

    Returns:
        pd.DataFrame: A DataFrame containing the `k` nearest coordinates to the given point.
    """
    distances = df.apply(lambda row: calculate_distance(
        (gw_row['x'], gw_row['y']),
        (row['x'], row['y'])
    ), axis=1)
    nearest_indices = distances.nsmallest(k).index
    return df.loc[nearest_indices]

# Creating a dataframe that stores all the associated features of the 487 stations.
data = pd.DataFrame()
def add_nearest_coordinates_column(df_to_add, name, k, df_to_merge=None):
    if df_to_merge is None:
        df_to_merge = data  # Use the current value of 'data' as the default
    results = []

    # Find the nearest stations according to the coordinates
    for _, gw_row in filtered_gw_coordinates.iterrows():
        nearest = find_nearest_coordinates(gw_row, df_to_add, k)
        nearest_list = nearest['hzbnr01'].tolist()
        results.append({
            'hzbnr01': gw_row['hzbnr01'],
            name: nearest_list
        })

    results_df = pd.DataFrame(results)

    # Debug: Check if 'hzbnr01' exists in both dataframes
    print("Columns in df_to_merge:", df_to_merge.columns)
    print("Columns in results_df:", results_df.columns)

    # Ensure that the column exists in both dataframes before merging
    if 'hzbnr01' in df_to_merge.columns and 'hzbnr01' in results_df.columns:
        # Merge operation
        df = df_to_merge.merge(results_df, on='hzbnr01', how='inner')

        # Debug: Birle?tirilmi? DataFrame'i yazd?rarak kontrol et
        print("Merged DataFrame:")
        print(df.head())
    else:
        raise KeyError("Column 'hzbnr01' does not exist in one of the dataframes.")

    return df

data = add_nearest_coordinates_column(gw_temp_coordinates, 'nearest_gw_temp', 1, df_to_merge=filtered_gw_coordinates)
data = add_nearest_coordinates_column(rain_coord, 'nearest_rain', 3, df_to_merge=data) # TODO burada data arguman? default oldugu icin silebiliriz.
data = add_nearest_coordinates_column(snow_coord, 'nearest_snow', 3, df_to_merge=data)
data = add_nearest_coordinates_column(source_fr_coord, 'nearest_source_fr', 1, df_to_merge=data)
data = add_nearest_coordinates_column(conduct_coord, 'nearest_conductivity', 1, df_to_merge=data)
data = add_nearest_coordinates_column(source_temp_coord, 'nearest_source_temp', 1, df_to_merge=data)
data = add_nearest_coordinates_column(surface_water_lvl_coord, 'nearest_owf_level', 3, df_to_merge=data)
data = add_nearest_coordinates_column(surface_water_temp_coord, 'nearest_owf_temp', 1, df_to_merge=data)
data = add_nearest_coordinates_column(sediment_coord, 'nearest_sediment', 1, df_to_merge=data)
data = add_nearest_coordinates_column(surface_water_fr_coord, 'nearest_owf_fr', 3, df_to_merge=data)
data.drop(["x", "y"], axis=1, inplace=True)

# For the .pkl file of the above dataframe named 'data'
file_path = os.path.join('Ehyd', 'pkl_files', 'data.pkl')
save_to_pickle(data, file_path)

########################################################################################################################
# Imputing NaN Values
########################################################################################################################
def nan_imputer(dict):
    """
    Imputes missing values in a dictionary of DataFrames by filling NaNs with the corresponding monthly means.

    Args:
        dict (dict): A dictionary where the keys are DataFrame names and the values are DataFrames
                     containing a 'Values' column with missing values represented as 'NaN'.

    Returns:
        dict: A dictionary with the same keys as the input, but with NaN values in each DataFrame
              replaced by the monthly mean of the 'Values' column.
    """
    new_dict = {}
    for df_name, df in dict.items():
        df_copy = df.copy(deep=True)  # Create a deep copy
        df_copy.replace('NaN', np.nan, inplace=True)
        first_valid_index = df_copy['Values'].first_valid_index()
        valid_values = df_copy.loc[first_valid_index:].copy()

        # Fill NaNs with the corresponding monthly means
        for month in range(1, 13):
            month_mean = valid_values[valid_values.index.month == month]['Values'].dropna().mean()
            valid_values.loc[valid_values.index.month == month, 'Values'] = valid_values.loc[
                valid_values.index.month == month, 'Values'].fillna(month_mean)

        # Update the copied DataFrame with filled values
        df_copy.update(valid_values)
        new_dict[df_name] = df_copy  # Store the modified copy

    return new_dict

filled_filtered_groundwater_dict = nan_imputer(filtered_groundwater_dict)
filled_gw_temp_dict = nan_imputer(gw_temp_dict)
filled_rain_dict = nan_imputer(rain_dict)
filled_snow_dict = nan_imputer(snow_dict)
filled_source_fr_dict = nan_imputer(source_fr_dict)
filled_source_temp_dict = nan_imputer(source_temp_dict)
filled_conduct_dict = nan_imputer(conduct_dict)
filled_surface_water_fr_dict = nan_imputer(surface_water_fr_dict)
filled_surface_water_lvl_dict = nan_imputer(surface_water_lvl_dict)
filled_surface_water_temp_dict = nan_imputer(surface_water_temp_dict)
filled_sediment_dict = nan_imputer(sediment_dict)

########################################################################################################################
# Adding lagged values and rolling means
########################################################################################################################
filled_dict_list = [filled_gw_temp_dict, filled_filtered_groundwater_dict, filled_snow_dict, filled_rain_dict,
                    filled_conduct_dict, filled_source_fr_dict, filled_source_temp_dict, filled_surface_water_lvl_dict,
                    filled_surface_water_fr_dict, filled_surface_water_temp_dict, filled_sediment_dict]

def add_lag_and_rolling_mean(df, window=6):
    """
    Adds lag features and rolling mean to a DataFrame.

    Args:
        df (pd.DataFrame): A DataFrame with at least one column, which will be used to create lag features
                           and compute rolling mean. The first column of the DataFrame will be used.
        window (int, optional): The window size for computing the rolling mean. Defaults to 6.

    Returns:
        pd.DataFrame: The original DataFrame with additional columns for lag features and rolling mean.
                      Includes lag features for 1, 2, and 3 periods and rolling mean columns with the specified window size.
    """
    column_name = df.columns[0]
    df['lag_1'] = df[column_name].shift(1)
    df['lag_2'] = df[column_name].shift(2)
    df['lag_3'] = df[column_name].shift(3)

    df["rolling_mean_original"] = df[column_name].rolling(window=window).mean()

    for i in range(1, 4):
        df[f'rolling_mean_{window}_lag_{i}'] = df["rolling_mean_original"].shift(i)
    return df

for dictionary in filled_dict_list:
    for key, df in dictionary.items():
        dictionary[key] = add_lag_and_rolling_mean(df)

########################################################################################################################
# Zero Padding and Data Type Change (float32)
########################################################################################################################
for dictionary in filled_dict_list:
    for key, df in dictionary.items():
        df.fillna(0, inplace=True)
        df = df.astype(np.float32)
        dictionary[key] = df

# For the making of .pkl files of the dictionaries in the list named 'filled_dict_list'
for dictionary in filled_dict_list:
    dict_name = [name for name in globals() if globals()[name] is dictionary][0]
    filename = os.path.join("Ehyd", "pkl_files", f'{dict_name}.pkl')
    save_to_pickle(dictionary, filename)

########################################################################################################################
# Creating two new dictionaries:
#   new_dataframes: is a dictionary storing DataFrames specific to each measurement station, containing both the
#                   station's data and associated features obtained from the data DataFrame.
#   monthly_dataframes: contains monthly versions of the data from new_dataframes, with keys representing months
#                   instead of measurement station IDs.
########################################################################################################################
data['hzbnr01'] = data['hzbnr01'].apply(lambda x: [x])

data_sources = {
    'nearest_gw_temp': ('gw_temp', filled_gw_temp_dict),
    'nearest_rain': ('rain', filled_rain_dict),
    'nearest_snow': ('snow', filled_snow_dict),
    'nearest_conductivity': ('conduct', filled_conduct_dict),
    'nearest_source_fr': ('source_fr', filled_source_fr_dict),
    'nearest_source_temp': ('source_temp', filled_source_temp_dict),
    'nearest_owf_level': ('owf_level', filled_surface_water_lvl_dict),
    'nearest_owf_temp': ('owf_temp', filled_surface_water_temp_dict),
    'nearest_owf_fr': ('owf_fr', filled_surface_water_fr_dict),
    'nearest_sediment': ('sediment', filled_sediment_dict)
}

new_dataframes = {}
for idx, row in data.iterrows():
    code = str(row['hzbnr01'][0])

    if code in filled_filtered_groundwater_dict:

        df = filled_filtered_groundwater_dict[code].copy()

        for key, (prefix, source_dict) in data_sources.items():
            for i, code_value in enumerate(row[key]):
                code_str = str(code_value)
                source_df = source_dict.get(code_str, pd.DataFrame())

                source_df = source_df.rename(columns=lambda x: f'{prefix}_{i + 1}_{x}')
                df = df.join(source_df, how='left')

                columns = ["Values", "lag_1", "lag_2", "lag_3", "rolling_mean_original", "rolling_mean_6_lag_1", "rolling_mean_6_lag_2", "rolling_mean_6_lag_3"]
                for column in columns:
                    if i == 2:
                        df[f"{prefix}_{column}_mean"] = (df[f"{prefix}_{i + 1}_{column}"] + df[f"{prefix}_{i}_{column}"] + df[f"{prefix}_{i - 1}_{column}"]) / 3

        new_dataframes[code] = df

monthly_dict_85to21 = {}
for year in range(1985, 2022):
    for month in range(1, 13):

        key = f"{year}_{month:02d}"

        monthly_data = []

        for df_id, df in new_dataframes.items():

            mask = (df.index.to_period("M").year == year) & (df.index.to_period("M").month == month)

            if mask.any():

                filtered_df = df[mask]

                new_index = [f"{df_id}" for i in range(len(filtered_df))]
                filtered_df.index = new_index

                monthly_data.append(filtered_df)

        if monthly_data:

            combined_df = pd.concat(monthly_data)

            monthly_dict_85to21[key] = combined_df

# Creating the .pkl of the monthly_dict_85to21
file_path = os.path.join("Ehyd", "pkl_files", 'monthly_dict_85to21.pkl')
save_to_pickle(monthly_dict_85to21, file_path)

file_path = os.path.join("Ehyd", "pkl_files", 'new_dataframes.pkl')
save_to_pickle(new_dataframes, file_path)

with open(os.path.join('Ehyd', 'pkl_files', 'new_dataframes.pkl'), 'rb') as file:
    new_dataframes = pickle.load(file)

########################################################################################################################
# SARIMA Model
########################################################################################################################

with open(os.path.join('Ehyd', 'pkl_files', 'monthly_dict_85to21.pkl'), 'rb') as file:
    monthly_dict_85to21 = pickle.load(file)

monthly_dict_with_correlation = monthly_dict_85to21.copy()

def average_correlation_feature_selection(data_dict, threshold=0.1):
    """
    Computes average correlation of features with the target variable across multiple dataframes and selects features
    based on a correlation threshold.

    Args:
        data_dict (dict): A dictionary where each value is a pandas DataFrame. Each DataFrame should contain a column
                          named 'Values' representing the target variable.
        threshold (float, optional): The minimum absolute correlation value required for a feature to be selected.
                                      Defaults to 0.1.

    Returns:
        list: A list of feature names that have an average correlation with the target variable above the specified
              threshold.
    """
    feature_corr_sum = None
    feature_count = 0

    for df in data_dict.values():
        corr_matrix = df.corr()
        target_corr = corr_matrix['Values'].drop('Values')

        if feature_corr_sum is None:
            feature_corr_sum = target_corr
        else:
            feature_corr_sum += target_corr

        feature_count += 1

    avg_corr = feature_corr_sum / feature_count

    selected_features = avg_corr[avg_corr.abs() > threshold].index.tolist()

    return selected_features

common_features = average_correlation_feature_selection(monthly_dict_with_correlation, threshold=0.4)  # 39

# hiperparametre optimizasyonu
# Yeni ba?lang?� tarihi
new_start_date = pd.to_datetime('1985-01-01')

# Yeni veri �er�eveleri s�zl�?�
adjusted_dataframes = {}

for key, df in new_dataframes.items():
    try:
        # Mevcut indeksin tarih format?na d�n�?t�r�lmesi
        df.index = pd.to_datetime(df.index)

        # Veriyi 1985-01-01 tarihinden itibaren filtreleme
        df_filtered = df[df.index >= new_start_date]

        # Yeni s�zl�?e ekleme
        adjusted_dataframes[key] = df_filtered
    except Exception as e:
        print(f"An error occurred with key {key}: {e}")

# adjusted_dataframes i�inde zaman serilerinin yeni ba?lang?� tarihi ile g�ncellenmi? halleri bulunur.


filtered_dataframes = {}

def filter_dataframe_by_features(df, features):
    """
    Filter the DataFrame columns by the specified feature list, while keeping the target column.

    Parameters:
        df (pd.DataFrame): The DataFrame to filter.
        features (list): List of column names to keep, excluding the target column.

    Returns:
        pd.DataFrame: Filtered DataFrame with the target column included.
    """
    # Target de?i?keninin ad?n? almak i�in ilk s�tunu ay?r?n
    target_column = df.columns[0]

    # Target de?i?keni hari� s�tunlar? belirleyin
    filtered_features = [target_column] + [col for col in features if col != target_column]

    # Belirlenen s�tunlar? se�in
    df_filtered = df[filtered_features]

    return df_filtered


for key, df in adjusted_dataframes.items():
    try:
        # Target de?i?keni ile birlikte common_features s�tunlar?n? filtreleyin
        filtered_df = filter_dataframe_by_features(df, common_features)
        filtered_dataframes[key] = filtered_df
    except KeyError as e:
        print(f"KeyError: {e} - Some columns in {key} are missing.")
    except Exception as e:
        print(f"An error occurred with key {key}: {e}")

for key, value in filtered_dataframes.items():
    print(value.head())

# filtered_dataframes art?k common_features ile filtrelenmi? veri �er�evelerini i�eriyor.









import itertools
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
import random

# Hyperparameter Optimization (Model Derecelerini Belirleme)
p = d = q = range(0, 2)
pdq = list(itertools.product(p, d, q))  # itertools.product kombolar? getiriyor
seasonal_pdq = [(x[0], x[1], x[2], 12) for x in list(itertools.product(p, d, q))]  # 12 ayda bir d�ng� tamamlan?yor

def sarima_optimizer_aic(train, exog, pdq, seasonal_pdq):
    best_aic, best_order, best_seasonal_order = float("inf"), None, None
    for param in pdq:
        for param_seasonal in seasonal_pdq:
            try:
                sarimax_model = SARIMAX(train, exog=exog, order=param, seasonal_order=param_seasonal)
                results = sarimax_model.fit(disp=0)
                aic = results.aic
                if aic < best_aic:
                    best_aic, best_order, best_seasonal_order = aic, param, param_seasonal
                print('SARIMA{}x{}12 - AIC:{}'.format(param, param_seasonal, aic))
            except Exception as e:
                print(f"Exception: {e} - SARIMA{param}x{param_seasonal}12")
                continue
    print('SARIMA{}x{}12 - AIC:{}'.format(best_order, best_seasonal_order, best_aic))
    return best_order, best_seasonal_order

results = {}

# Rastgele 20 veri �er�evesi se�
sampled_keys = random.sample(list(filtered_dataframes.keys()), 10)

for df_id in sampled_keys:
    df = filtered_dataframes[df_id]
    if not df.empty:
        # Target s�tunu ve di?er s�tunlar? ay?r
        train = df['Values']
        exog = df.drop(columns=['Values'])  # 'Values' s�tunu d???ndaki di?er s�tunlar
        # Hiperparametre optimizasyonunu yap
        best_order, best_seasonal_order = sarima_optimizer_aic(train, exog, pdq, seasonal_pdq)
        results[df_id] = {
            'Best Order': best_order,
            'Best Seasonal Order': best_seasonal_order
        }
    else:
        results[df_id] = {
            'Best Order': None,
            'Best Seasonal Order': None
        }

# Sonu�lar? yazd?r
for df_id, res in results.items():
    print(f'DataFrame ID: {df_id}')
    print(f'Best Order: {res["Best Order"]}')
    print(f'Best Seasonal Order: {res["Best Seasonal Order"]}')
    print('---')


# Genel olarak, ilk deneme i�in (1, 0, 1) ve (0, 1, 1, 12)
# kombinasyonu iyi bir ba?lang?� noktas? gibi g�r�n�yor ��nk� bir�ok veri setinde bu kombinasyonun iyi �al??t??? g�z�k�yor.





for month, df in monthly_dict_with_correlation.items():
    monthly_dict_with_correlation[month] = df[ ['Values'] + common_features]

print(monthly_dict_with_correlation['2021_12'].head())
print(monthly_dict_with_correlation['2021_12'].shape)

# Test months to forecast
forecast_months = ['2020_01', '2020_02', '2020_03', '2020_04', '2020_05', '2020_06',
                   '2020_07', '2020_08', '2020_09', '2020_10', '2020_11', '2020_12',
                   '2021_01', '2021_02', '2021_03', '2021_04', '2021_05', '2021_06',
                   '2021_07', '2021_08', '2021_09', '2021_10', '2021_11', '2021_12']

train_data = {month: df for month, df in monthly_dict_with_correlation.items() if month not in forecast_months}

train_data = {k: v for k, v in train_data.items() if k >= "2000_01"}


all_data = pd.concat([df for df in train_data.values()])

# Her istasyon i�in 24 ayl?k tahmin yapma
forecasts = {}
for station in all_data.index.unique():
    # ?stasyon verilerini al
    station_data = all_data.loc[station]

    # Modeli olu?turma ve e?itme
    model = SARIMAX(
        station_data['Values'],  # Hedef de?i?ken
        exog=station_data.drop(columns=['Values']),  # Di?er �zellikler
        order=(1, 0, 1),  # ARIMA parametreleri
        seasonal_order=(0, 1, 1, 12)  # Mevsimsel ARIMA parametreleri
    )
    model_fit = model.fit(disp=False)

    # 24 ayl?k tahmin yap
    forecast = model_fit.get_forecast(steps=24, exog=station_data.drop(columns=['Values']).values[
                                                     -24:])  # Son 24 ay?n exog de?erleri
    forecast_values = forecast.predicted_mean

    # Tahmin sonu�lar?n? sakla
    forecasts[station] = forecast_values

# Tahmin sonu�lar?n? DataFrame'e ekleme
forecast_df = pd.DataFrame(forecasts).T
forecast_df.columns = [f'forecast_month_{i + 1}' for i in range(24)]

# Sonu�lar? yazd?rma
print(forecast_df)

# Test verilerini birle?tirme
test_data = {month: df for month, df in monthly_dict_with_correlation.items() if month in forecast_months}
test_data = pd.concat([df for df in test_data.values()])


# SMAPE hesaplama fonksiyonu
def smape(y_true, y_pred):
    return 100 * np.mean(2 * np.abs(y_pred - y_true) / (np.abs(y_true) + np.abs(y_pred)))


# SMAPE de?erlerini hesaplama
# SMAPE hesaplama fonksiyonu
def smape(y_true, y_pred):
    return 100 * np.mean(2 * np.abs(y_pred - y_true) / (np.abs(y_true) + np.abs(y_pred)))


# Genel SMAPE hesaplama
all_actual = []
all_predicted = []

for station in forecast_df.index:
    # Ger�ek de?erleri al
    actual_values = test_data.loc[station, 'Values'].values
    predicted_values = forecast_df.loc[station].values

    # De?erleri listeye ekle
    all_actual.extend(actual_values)
    all_predicted.extend(predicted_values)

# Genel SMAPE de?erini hesapla
general_smape = smape(np.array(all_actual), np.array(all_predicted))
print(f"Genel SMAPE: {general_smape:.2f}%")
# 0.21 %

# Belirli bir istasyon kodu i�in grafik �izme
def plot_forecast(station_code):
    # Ger�ek de?erleri al
    actual_values = test_data.loc[station_code, 'Values'].values
    predicted_values = forecast_df.loc[station_code].values

    # Tarih aral???n? olu?tur
    forecast_months = pd.date_range(start='2020-01-01', periods=24, freq='M')

    # Grafik �izimi
    plt.figure(figsize=(12, 6))
    plt.plot(forecast_months, actual_values, label='Ger�ek De?erler', marker='o')
    plt.plot(forecast_months, predicted_values, label='Tahmin De?erleri', marker='x')
    plt.title(f"{station_code} i�in Ger�ek ve Tahmin De?erleri")
    plt.xlabel("Tarih")
    plt.ylabel("De?er")
    plt.legend()
    plt.grid()
    plt.show()


# �rnek olarak belirli bir istasyon kodu se�me
station_code_to_plot = '321430'  # Buraya istedi?iniz istasyon kodunu yaz?n
plot_forecast(station_code_to_plot)


