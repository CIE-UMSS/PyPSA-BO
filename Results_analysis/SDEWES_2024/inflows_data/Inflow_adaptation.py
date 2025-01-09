#%% import libraries
import xarray as xr
import pandas as pd
import numpy as np

#%% load control inflow
control_inflow_path = r"C:\Users\Carlos\Desktop\PyPSA-BO\Results_analysis\SDEWES_2024\inflows_data\SDDP_scaledinflows_control.csv"
control_inflow = pd.read_csv(control_inflow_path, header = 0,sep=";")
control_inflow

#%% Define list with basin and powerplant correspondence
Catchments = pd.DataFrame(index=[1,2,3,4,5,6,7,8,9])
Catchments["Basins"] = ["UH-2-28", "UH-2-34","UH-2-31","UH-2-40","UH-2-56","UH-2-54","UH-2-58","UH-3-14-3","UH-3-2"]
Catchments["Powerplants"] = [("ZON", "TIQ", "BOT", "CUT", "SRO1", "SRO2*", "SAI", "CHU*", "HAR", "CAH", "HUA"), ("CHJ", "YAN"),
                             ("MIG", "ANG", "CHO", "CRB", "UMA", "PLD"), ("QHE"), ("KAN", "MIS"), ("SIS", "COR", "SJS", "SJE"),
                             ("SEH", "JUN"), ("KIL", "LAN", "PUH*"), ("SJA")]
Catchments


#%% Function to load change factors and create new inflows

def inflow_adaptation(year, event): 
    #year can be "2030", "2040" or "2050" (integer number); event can be "EN" or "LN" (string) 
    change_factor_path = "C://Users//Carlos//Desktop//PyPSA-BO//Results_analysis//SDEWES_2024//inflows_data//changefactors_" + str(event) + str(year) + ".xlsx"
    change_factor = pd.read_excel(change_factor_path)

    new_inflow = control_inflow.copy()

    for col in new_inflow.columns :
        for i in Catchments.index :
            if col in Catchments.loc[i,"Powerplants"] :
                basin = (Catchments.loc[i,"Basins"])
                new_inflow[col] = new_inflow[col]*change_factor.loc[12,basin]
    
    return new_inflow


#%% Save modified inflows 

for y in (2030,2040,2050) :
    for e in ("EN","LN") :
        adapted_inflow_path = "C://Users//Carlos//Desktop//PyPSA-BO//Results_analysis//SDEWES_2024//inflows_data//scaledinflows_" + str(e) + str(y) + ".csv"
        adapted_inflow = inflow_adaptation(y,e)
        adapted_inflow.to_csv(adapted_inflow_path, sep=";", index=False)


# %%


# %%
