# IMPORTS
import os
import warnings
from statsmodels.tools.sm_exceptions import ConvergenceWarning
warnings.simplefilter('ignore', category=ConvergenceWarning)
import pandas as pd
from datetime import datetime
from scipy.spatial import distance
from collections import Counter
import seaborn as sns
import itertools
import pickle
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.statespace.sarimax import SARIMAX
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.float_format', lambda x: '%.3f' % x)
pd.set_option('display.max_colwidth', None)
pd.set_option('display.width', 500)
from sklearn.model_selection import train_test_split
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense



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

                                value_str = value_str.strip().replace('L�cke', 'NaN')  # Convert 'L�cke' to NaN

                                # Skip rows with invalid data or specific keywords
                                if any(keyword in value_str for keyword in ["F", "K", "rekonstruiert aus Version 3->"]):
                                    continue

                                # Convert value to float
                                try:
                                    value = np.float32(value_str.replace(',', '.'))
                                except ValueError:
                                    continue

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

def to_monthly(df_dict):
    for df_name, df_value in df_dict.items():
        df_value['Date'] = pd.to_datetime(df_value['Date'])
        df_value.set_index('Date', inplace=True)
        df_dict[df_name] = df_value.resample('M').mean()  # Do?rudan s�zl�?� g�ncelle
    return df_dict

def date_to_index(df_dict):
    for df_name, df_value in df_dict.items():
        df_value['Date'] = pd.to_datetime(df_value['Date'])
        df_value.set_index('Date', inplace=True)
    return df_dict



def filter_dataframes_by_points(dataframes_dict, points_list):
    """
    Filters a dictionary of DataFrames to include only those whose names are specified in a given CSV file.

    Args:
        dataframes_dict (dict): A dictionary where keys are names (str) and values are DataFrames.
        points_list (str): Path to a CSV file that contains the names (str) of the DataFrames to filter.

    Returns:
        dict: A filtered dictionary containing only the DataFrames whose names are listed in the CSV file.
    """
    filtered_dict = {name: df for name, df in dataframes_dict.items() if name in points_list}
    return filtered_dict

#####################################
# Creating Dataframes from given CSVs
#####################################

##################################### Groundwater
groundwater_all_coordinates = station_coordinates("Groundwater")

# Groundwater Level
groundwater_folder_path = os.path.join("Ehyd", "datasets_ehyd", "Groundwater", "Grundwasserstand-Monatsmittel")
groundwater_dict, groundwater_coordinates = to_dataframe(groundwater_folder_path, groundwater_all_coordinates)
groundwater_dict = date_to_index(groundwater_dict)
to_global(groundwater_dict, prefix="gw_")

# Groundwater Temperature
groundwater_temperature_folder_path = os.path.join("Ehyd", "datasets_ehyd", "Groundwater", "Grundwassertemperatur-Monatsmittel")
groundwater_temperature_dict, groundwater_temperature_coordinates = to_dataframe(groundwater_temperature_folder_path, groundwater_all_coordinates)
groundwater_temperature_dict = date_to_index(groundwater_temperature_dict)
to_global(groundwater_temperature_dict, prefix="gwt_")

# Creating new dictionaries according to requested stations
points = pd.read_csv(os.path.join("Ehyd", "datasets_ehyd", "gw_test_empty.csv"))
points_list = [col for col in points.columns[1:]]

filtered_groundwater_dict = filter_dataframes_by_points(groundwater_dict, points_list)
filtered_gw_coordinates = groundwater_coordinates[groundwater_coordinates['hzbnr01'].isin([int(i) for i in points_list])]

##################################### Precipitation
precipitation_coordinates = station_coordinates("Precipitation")

# Rain
rain_folder_path = os.path.join("Ehyd", "datasets_ehyd", "Precipitation", "N-Tagessummen")
rain_dict, rain_coordinates = to_dataframe(rain_folder_path, precipitation_coordinates)
rain_dict_monthly = to_monthly(rain_dict)
to_global(rain_dict_monthly, prefix="rain_")

# Snow
snow_folder_path = os.path.join("Ehyd", "datasets_ehyd", "Precipitation", "NS-Tagessummen")
snow_dict, snow_coordinates = to_dataframe(snow_folder_path, precipitation_coordinates)
snow_dict_monthly = to_monthly(snow_dict)
to_global(snow_dict_monthly, prefix="snow_")


##################################### Sources
sources_coordinates = station_coordinates("Sources")

# Flow Rate
source_flow_rate_path = os.path.join("Ehyd", "datasets_ehyd", "Sources", "Quellsch�ttung-Tagesmittel")
source_flow_rate_dict, source_flow_rate_coordinates = to_dataframe(source_flow_rate_path, sources_coordinates)
source_flow_rate_dict_monthly = to_monthly(source_flow_rate_dict)
to_global(source_flow_rate_dict_monthly, prefix="source_fr_")

# Conductivity
conductivity_folder_path = os.path.join("Ehyd", "datasets_ehyd", "Sources", "Quellleitf�higkeit-Tagesmittel")
conductivity_dict, conductivity_coordinates = to_dataframe(conductivity_folder_path, sources_coordinates)
conductivity_dict_monthly = to_monthly(conductivity_dict)
to_global(conductivity_dict_monthly, prefix="conductivity_")

# Source Temperature
source_temp_folder_path = os.path.join("Ehyd", "datasets_ehyd", "Sources", "Quellwassertemperatur-Tagesmittel")
source_temp_dict, source_temp_coordinates = to_dataframe(source_temp_folder_path, sources_coordinates)
source_temp_dict_monthly = to_monthly(source_temp_dict)
to_global(source_temp_dict_monthly, prefix="source_temp_")

##################################### Surface Water

surface_water_coordinates = station_coordinates("Surface_Water")

# Surface Water Level
surface_water_level_folder_path = os.path.join("Ehyd", "datasets_ehyd", "Surface_Water", "W-Tagesmittel")
surface_water_level_dict, surface_water_level_coordinates = to_dataframe(surface_water_level_folder_path, surface_water_coordinates)
surface_water_level_dict_monthly = to_monthly(surface_water_level_dict)
to_global(surface_water_level_dict, prefix="surface_water_level")

# Surface Water Temperature
surface_water_temp_folder_path = os.path.join("Ehyd", "datasets_ehyd", "Surface_Water", "WT-Monatsmittel")
surface_water_temp_dict, surface_water_temp_coordinates = to_dataframe(surface_water_temp_folder_path, surface_water_coordinates)
surface_water_temp_dict = date_to_index(surface_water_temp_dict)

to_global(surface_water_temp_dict, prefix="surface_water_temp")

# Sediment
sediment_folder_path = os.path.join("Ehyd", "datasets_ehyd", "Surface_Water", "Schwebstoff-Tagesfracht")
sediment_dict, sediment_coordinates = to_dataframe(sediment_folder_path, surface_water_coordinates)  # daily version
sediment_dict_monthly = to_monthly(sediment_dict)
to_global(sediment_dict_monthly, prefix="sediment_")

# Surface Water Flow Rate
surface_water_flow_rate_folder_path = os.path.join("Ehyd", "datasets_ehyd", "Surface_Water", "Q-Tagesmittel")
surface_water_flow_rate_dict, surface_water_flow_rate_coordinates = to_dataframe(surface_water_flow_rate_folder_path, surface_water_coordinates)
surface_water_flow_rate_dict_monthly = to_monthly(surface_water_flow_rate_dict)
to_global(surface_water_flow_rate_dict, prefix="surface_water_fr_")

########################################################################################################################
# Gathering associated features for 487 stations
########################################################################################################################

def calculate_distance(coord1, coord2):
    return distance.euclidean(coord1, coord2)

def find_nearest_coordinates(gw_row, df, k=20):
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

    # Find the nearest points according to the coordinates
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

data = add_nearest_coordinates_column(groundwater_temperature_coordinates, 'nearest_gw_temp', 1, df_to_merge=filtered_gw_coordinates)
data = add_nearest_coordinates_column(rain_coordinates, 'nearest_rain', 3, df_to_merge=data) # TODO burada data arguman? default oldugu icin silebiliriz.
data = add_nearest_coordinates_column(snow_coordinates, 'nearest_snow', 3, df_to_merge=data)
data = add_nearest_coordinates_column(source_flow_rate_coordinates, 'nearest_source_fr', 1, df_to_merge=data)
data = add_nearest_coordinates_column(conductivity_coordinates, 'nearest_conductivity', 1, df_to_merge=data)
data = add_nearest_coordinates_column(source_temp_coordinates, 'nearest_source_temp', 1, df_to_merge=data)
data = add_nearest_coordinates_column(surface_water_level_coordinates, 'nearest_owf_level', 3, df_to_merge=data)
data = add_nearest_coordinates_column(surface_water_temp_coordinates, 'nearest_owf_temp', 1, df_to_merge=data)
data = add_nearest_coordinates_column(sediment_coordinates, 'nearest_sediment', 1, df_to_merge=data)
data = add_nearest_coordinates_column(surface_water_flow_rate_coordinates, 'nearest_owf_fr', 3, df_to_merge=data)
data.drop(["x", "y"], axis=1, inplace=True)

data.to_csv('data.csv', index=False)




# yer alt? suyu s?cakl?k tur?usu i�in
data['nearest_gw_temp'].explode().nunique()  # 276

# data_gw_temp_dict isimli yeni s�zl�?� olu?turuyoruz
data_gw_temp_dict = {}

# nearest_gw_temp kolonundaki her bir listeyi d�ng� ile al?yoruz
for key_list in data['nearest_gw_temp']:
    # Liste i�indeki her bir de?eri string'e �evirip kontrol ediyoruz
    for key in key_list:
        str_key = str(key)
        # E?er str_key groundwater_temperature_dict'te varsa, bu key ve ilgili dataframe'i yeni s�zl�?e ekle
        if str_key in groundwater_temperature_dict:
            data_gw_temp_dict[str_key] = groundwater_temperature_dict[str_key]

len(data_gw_temp_dict)  # 276




########################################################################################################################
# Investigating the dataframes
########################################################################################################################
def is_monoton(dict):
    for df_name, value in dict.items():
        if value.index.name != 'Date':
            if not value['Date'].is_monotonic_increasing:
                print(f"{df_name} monoton art?? g�stermiyor. Bu konuda bir aksiyon al?nmal?")
            if 'Date' not in value.columns:
                print(f"---- {dict}{df_name} index veya s�tun olarak 'Date' mevcut de?il.")
                continue
            continue
        if not value.index.is_monotonic_increasing:
            print(f"{df_name} monoton art?? g�stermiyor. Bu konuda bir aksiyon al?nmal?")

is_monoton(filtered_groundwater_dict)
is_monoton(groundwater_temperature_dict)
is_monoton(rain_dict)
is_monoton(snow_dict)
is_monoton(source_flow_rate_dict)
is_monoton(conductivity_dict)
is_monoton(source_temp_dict)
is_monoton(surface_water_level_dict)
is_monoton(surface_water_temp_dict)
is_monoton(sediment_dict)
is_monoton(surface_water_flow_rate_dict)


def plot_row_count_distribution(df_dict):
    """
    Bu fonksiyon, verilen s�zl�kteki DataFrame'lerin sat?r say?lar?n?n da??l?m?n? histogram olarak �izer.

    Parametre:
    df_dict (dict): Anahtarlar?n string, de?erlerin ise pandas DataFrame oldu?u bir s�zl�k.
    """
    # DataFrame'lerin sat?r say?lar?n? hesaplay?n
    row_counts = [df.shape[0] for df in df_dict.values()]

    # Sat?r say?lar?n?n da??l?m?n? histogram olarak �izin
    plt.hist(row_counts, bins=10, edgecolor='black')
    plt.xlabel('Sat?r Say?s?')
    plt.ylabel('Frekans')
    plt.title('DataFrame Sat?r Say?lar?n?n Da??l?m?')
    plt.show()

plot_row_count_distribution(filtered_groundwater_dict)


shapes = []
dates = []

for df_name, value in filtered_groundwater_dict.items():
    shapes.append(value.shape[0])
    dates.append(value["Date"].min())

print(f"min: {min(shapes)} ay say?s?")
print(f"max: {max(shapes)} ay say?s?")
max(dates)  # max, min y?l 2001


for df_name, df in sediment_dict.items():
    nan_rows = df[df.isnull().any(axis=1)]
    print(f"DataFrame: {df_name}")
    print(f"Toplam NaN say?s?: {df.isnull().sum()}")
    print(nan_rows)


########################################################################################################################
# Imputing Missing Values with SARIMA()
########################################################################################################################

def fill_missing_values_with_sarima(df_dict):
    """
    Verilen DataFrame'lerdeki eksik de?erleri SARIMA modeli kullanarak doldurur.

    Args:
    df_dict (dict): Anahtarlar? DataFrame adlar?, de?erleri DataFrame'ler olan bir s�zl�k.

    Returns:
    dict: Eksik de?erleri doldurulmu? DataFrame'leri i�eren bir s�zl�k.
    """
    filled_dfs = {}

    for key, df in df_dict.items():
        # SARIMA model parametrelerini belirleme
        p = d = q = range(0, 2)
        pdq = list(itertools.product(p, d, q))
        seasonal_pdq = [(x[0], x[1], x[2], 12) for x in list(itertools.product(p, d, q))]

        best_aic = np.float32("inf")
        best_param = None
        best_seasonal_param = None

        # Grid Search ile en iyi SARIMA parametrelerini bulma
        for param in pdq:
            for seasonal_param in seasonal_pdq:
                try:
                    model = SARIMAX(df['Values'],
                                    order=param,
                                    seasonal_order=seasonal_param,
                                    enforce_stationarity=False,
                                    enforce_invertibility=False)
                    results = model.fit(disp=False)
                    if results.aic < best_aic:
                        best_aic = results.aic
                        best_param = param
                        best_seasonal_param = seasonal_param
                except:
                    continue

        # En iyi parametrelerle SARIMA modelini olu?turma
        sarima_model = SARIMAX(df['Values'],
                               order=best_param,
                               seasonal_order=best_seasonal_param)
        sarima_result = sarima_model.fit(disp=False)

        # Eksik de?erleri doldurma
        df['Values_Filled'] = sarima_result.predict(start=df.index[0], end=df.index[-1])
        df['final_values'] = df['Values'].combine_first(df['Values_Filled'])
        df = df["final_values"]
        filled_dfs[key] = df

    return filled_dfs


# Fonksiyonun kullan?m?
filled_sediment_dict_monthly = fill_missing_values_with_sarima(sediment_dict_monthly)
filled_surface_water_level_dict_monthly = fill_missing_values_with_sarima(surface_water_level_dict_monthly)
filled_surface_water_flow_rate_dict_monthly = fill_missing_values_with_sarima(surface_water_flow_rate_dict_monthly)
filled_surface_water_temp_dict = fill_missing_values_with_sarima(surface_water_temp_dict)
# bunda bir uyar? verdi uyar?n?n ��z�m�: df.index = pd.date_range(start='2020-01-01', periods=len(df), freq='MS')
# biz frekans belirtmedi?imiz i�in ayl?k oldu?unu tahmin ediyormu?
filled_groundwater_dict = fill_missing_values_with_sarima(filtered_groundwater_dict)
filled_snow_dict_monthly = fill_missing_values_with_sarima(snow_dict_monthly)
filled_data_gw_temp_dict = fill_missing_values_with_sarima(data_gw_temp_dict)
filled_conductivity_dict = fill_missing_values_with_sarima(conductivity_dict_monthly)
filled_source_flow_rate_dict = fill_missing_values_with_sarima(source_flow_rate_dict_monthly)
filled_source_temp_dict = fill_missing_values_with_sarima(source_temp_dict_monthly)
filled_rain_dict = fill_missing_values_with_sarima(rain_dict_monthly)




# write pickle
with open('filled_sediment_dict_monthly.pkl', 'wb') as f:
    pickle.dump(filled_sediment_dict_monthly, f)

with open('filled_surface_water_level_dict_monthly.pkl', 'wb') as f:
    pickle.dump(filled_surface_water_level_dict_monthly, f)

with open('filled_surface_water_flow_rate_dict_monthly.pkl', 'wb') as f:
    pickle.dump(filled_surface_water_flow_rate_dict_monthly, f)

with open('filled_surface_water_temp_dict.pkl', 'wb') as f:
    pickle.dump(filled_surface_water_temp_dict, f)

with open('filled_groundwater_dict.pkl', 'wb') as f:
    pickle.dump(filled_groundwater_dict, f)

with open('filled_snow_dict_monthly.pkl', 'wb') as f:
    pickle.dump(filled_snow_dict_monthly, f)

with open('filled_data_gw_temp_dict.pkl', 'wb') as f:
    pickle.dump(filled_data_gw_temp_dict, f)

with open('filled_conductivity_dict.pkl', 'wb') as f:
    pickle.dump(filled_conductivity_dict, f)

with open('filled_source_flow_rate_dict.pkl', 'wb') as f:
    pickle.dump(filled_source_flow_rate_dict, f)

with open('filled_source_temp_dict.pkl', 'wb') as f:
    pickle.dump(filled_source_temp_dict, f)

with open('filled_rain_dict.pkl', 'wb') as f:
    pickle.dump(filled_rain_dict, f)



###############################################################################################################
###############################################################################################################
############################# TURSUDAN SONRASINI �ALI?TIRAB?L?R?Z #############################################
###############################################################################################################
###############################################################################################################
# Pickle dosyalar?n? toplu a�ma i?lemi:
pkl_files = [f for f in os.listdir() if f.endswith('.pkl')]

for pkl_file in pkl_files:
    with open(pkl_file, 'rb') as file:
        var_name = pkl_file[:-4]
        globals()[var_name] = pickle.load(file)

data = pd.read_csv("data.csv")

#######################################################################

# 0. lstm'ye girecek ayl?k dataseti iskeletlerini haz?rla
# 1. bu a?a??dakileri dene,
# 2. yeralt? su seviyeleri ile korelasyonlar?na bak
# 3. her noktan?n en iyi korele oldu?u s�tunu se�
# 4. lstm'ye girecek final verisetine o s�tunu koy ya?mur i�in.
# 5. bunu kar, sediment vs i�in de yap.

#######################################################################
# s�zl�klerin i�indeki serileri dataframe yap?yorum.
dict_list = [filled_conductivity_dict, filled_data_gw_temp_dict, filled_groundwater_dict, filled_rain_dict,
             filled_sediment_dict_monthly, filled_snow_dict_monthly, filled_source_flow_rate_dict,
             filled_source_temp_dict, filled_surface_water_flow_rate_dict_monthly,
             filled_surface_water_level_dict_monthly, filled_surface_water_temp_dict]


# Dict list i�indeki her bir s�zl�?�n value'lar?n? DataFrame yapacak fonksiyon
def convert_series_to_dataframe(d):
    for key in d:
        d[key] = d[key].to_frame(name=key)
    return d

for i in range(len(dict_list)):
    dict_list[i] = convert_series_to_dataframe(dict_list[i])


# Lag ve rolling mean hesaplamalar?n? ger�ekle?tirecek fonksiyon
def add_lag_and_rolling_mean(df, window=6):
    # ?lk s�tunun ad?n? al
    column_name = df.columns[0]
    # 1 lag'li versiyonu ekle
    df[f'lag_1'] = df[column_name].shift(1)
    # Lag'li ve rolling mean s�tunlar?n? ekle
    for i in range(1, 2):  # Burada 1 lag'li oldu?u i�in range(1, 2) kullan?yoruz.
        df[f'rolling_mean_{window}_lag_{i}'] = df[column_name].shift(i).rolling(window=window).mean()
    return df


for d in dict_list:
    for key, df in d.items():
        d[key] = add_lag_and_rolling_mean(df)


def zero_padding(df, start_date='1960-01-01'):
    # E?er indeks zaten PeriodIndex de?ilse, to_period('M') yap
    if not isinstance(df.index, pd.PeriodIndex):
        df.index = df.index.to_period('M')

    # Belirlenen ba?lang?� tarihi
    start_date = pd.to_datetime(start_date).to_period('M')

    # Tarih aral???n? geni?let
    all_dates = pd.period_range(start=start_date, end=df.index.max(), freq='M')

    # Yeni tarih aral??? i�in bo? bir veri �er�evesi olu?tur
    new_df = pd.DataFrame(index=all_dates)

    # Eski veri �er�evesini yeni veri �er�evesine birle?tir
    new_df = new_df.join(df, how='left').fillna(0)

    # Periyotlar? datetime'e d�n�?t�r
    new_df.index = new_df.index.to_timestamp()

    return new_df

# Her bir s�zl�kteki veri �er�evelerini g�ncelleme
for dictionary in dict_list:
    for key in dictionary:
        dictionary[key] = zero_padding(dictionary[key])

# # G�ncellenmi? s�zl�kleri kontrol et
# for key, df in filled_snow_dict_monthly.items():
#     print(f"{key}:")
#     print(df.tail(15))  # Ba?lang?�ta birka� sat?r? g�sterir
#     print()


###############
# 11 s�zl�kteki t�m dataframe'lerin t�m kolonlar?n? float32'ye �evirme
def convert_to_float32(df):
    return df.astype('float32')

# Her bir s�zl�kteki veri �er�evelerini veri tipini float32'ye �evirme
for dictionary in dict_list:
    for key in dictionary:
        # Veri tipini float32'ye �evir
        dictionary[key] = convert_to_float32(dictionary[key])


# # float 32 check etmek i�in
# def check_dtypes(df):
#     return df.dtypes
# # G�ncellenmi? veri �er�evelerinin veri tiplerini kontrol etme
# for dictionary in dict_list:
#     for key, df in dictionary.items():
#         print(f"{key}:")
#         print("Data Types:")
#         print(check_dtypes(df))  # Veri tiplerini kontrol eder
#         print()


#### dataframe'leri indexlerine g�re birle?tirece?im i�in hepsinde t?pat?p ayn? indeks mi var ona bakaca??m
# kafamdaki plan:
#### 487 dataframe yapal?m ve bir listeye alal?m ya da tam tersi 720 tanesini al?p bir listeye koyal?m ( bu daha mant?kl? ��nk� sonra transpose'unu almak zorunda kalmay?z)


###################################################
# Birden fazla s�zl�kten belirli bir ay?n 'val' s�tunlar?n? toplamak i�in bir fonksiyon

def get_monthly_vals(dict_list, year, month):
    monthly_vals = []
    for data_dict in dict_list:
        for df_name, df in data_dict.items():
            df.index = pd.to_datetime(df.index)  # Tarih indeksine sahip oldu?undan emin olun
            for i in df.columns:
                monthly_data = df[(df.index.year == year) & (df.index.month == month)][i]
                monthly_vals.append(monthly_data)
    if monthly_vals:
        return pd.concat(monthly_vals, axis=1)
    else:
        return pd.DataFrame()


# �rne?in, 2023 y?l? Ocak ay? verilerini almak i�in
monthly_vals = get_monthly_vals(dict_list, 2021, 12)
monthly_vals.shape
#### Normalizasyon yani scaling yapmam?z gerek
####################################################


#### LSTM - omg it's happening
# 1. Veri Haz?rl???
# 'dataframes' bir liste olarak t�m DataFrame'lerinizi i�erir
dataframes = [df1, df2, ..., df487]

# DataFrame'leri numpy array'lerine d�n�?t�r�p birle?tirin
data = np.array([df.values for df in dataframes])  # (720, 487, 5)

# 2. Pencereleme
def create_windows(data, window_size, forecast_horizon):
    X, y = [], []
    num_time_steps = data.shape[0]

    for start in range(num_time_steps - window_size - forecast_horizon + 1):
        end = start + window_size
        X.append(data[start:end, :, :])
        y.append(data[end:end + forecast_horizon, :, :])

    return np.array(X), np.array(y)


window_size = 12 # window size'? hala tam olarak anlayamad?m
forecast_horizon = 26 # �n�m�zdeli 26 ay? tahmin edece?iz
X, y = create_windows(data, window_size, forecast_horizon)  # X: (672, 12, 487, 5), y: (672, 26, 487, 5)

# 3. E?itim ve Test Setlerine B�lme
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

# 4. LSTM Modelini Olu?turma ve E?itme
model = Sequential()
model.add(LSTM(units=50, return_sequences=True, input_shape=(window_size, data.shape[1], data.shape[2])))
model.add(LSTM(units=50, return_sequences=True))
model.add(Dense(data.shape[2]))  # �?k?? katman?, tahmin edilmesi gereken s�tun say?s?na g�re ayarlanmal?
model.compile(optimizer='adam', loss='mse')

# Modeli e?itme
history = model.fit(X_train, y_train, epochs=50, batch_size=32, validation_data=(X_test, y_test))


