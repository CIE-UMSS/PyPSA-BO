Changes made:
*Load year is changed based on the newprofile2020 year data set (9.968 TWh based on 2021) and values for each year are modified with the scaling factors of 0.948, 1.348, 1.697 and 2.032 for 2020, 2030, 2040 and 2050 respectively - demands are expected to be 13.44 (2030), 16.92 (2040) and 20.26 (2050)
*custom_powerplants file is exchanged for each scenario based on the year selected. Each custom_powerplants file considers expansions and reduced capacities due to planned or decomissioned power plants in each deacade.
*inflows for the projection use inflow data from SDDP for the year 2013 as the control value and, depending on the event, change factors for each basin are applied to powerplants based on their location - inflows avialable are e.g. scaledinflows_EN2030.csv, scaledinflows_LN2050.csv, or SDDP_scaledinflows_control.csv)
*inflows are introduced in the model based on the scenario considered and the modifications made were done in script (add_electricity script)
*