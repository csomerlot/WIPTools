# ---------------------------------------------------------------------------
# TopoHydro.py
# Created on: Fri Feb 16 2007 10:07:43 AM
#   (generated by ArcGIS/ModelBuilder)
# Usage: TopoHydro <Input_DEM> <Mask> <Threshold_for_stream_formation__acres_> <Streams_Output_Raster> <Cumulative_Drainage__Flow_Acc__Output_Raster> <Output_flow_direction_raster> 
# Description: 
# Creates the stream network and flow accumulation grids to be used as stand-alone products or in subsequent tools
# ---------------------------------------------------------------------------

# Import system modules
import sys, os
import Helper
from time import sleep
import arcpy
from arcpy import env
from arcpy.sa import *

#~ print sys.argv
#~ os.chdir(os.path.split(sys.argv[0])[0])
        
hp = Helper.Helper(sys.argv)

try:
      
    # Save hp.Workspace...
    if sys.argv[1].endswith('.mdb'):
        #~ hp.log("\n\nWorkspace must be a directory\n\n")
        raise
    if sys.argv[1] == "#":
        WS = os.path.split(sys.argv[2])[0]
    else:
        WS = sys.argv[1]
    hp.Workspace = WS
    if sys.argv[4] == '#' and sys.argv[5]== "":
        raise Exception, "You must select either a threshold for stream or manually delineated stream."    
    

    # Clean out old geodatabase files
    for mdb in os.listdir(WS):
        if mdb.endswith(".mdb"):
            if mdb == "WIPoutput.mdb" or mdb.startswith("CIPresults"):
                gdb = os.path.join(WS, mdb)
                #~ hp.logfile.write(mdb+'\n\n')
                arcpy.Delete_management(gdb)
                #~ os.system('del "%s"' % gdb)
                sleep(3)
                if os.path.exists(gdb):
                    #~ hp.log('\n\nCould not delete %s, do it manually\n\n' % mdb)
                    raise
                #~ else:
                    #~ hp.log(" Deleted " + gdb)
    
    datfile = os.path.join(WS, "WIP.dat")
    if os.path.exists(datfile): 
        os.remove(datfile)
        os.system('del WIP.dat')

    # Parse input params
    tempdem = sys.argv[2]
    ThisMask = sys.argv[3]
    Threshold_for_stream_formation__acres_ = sys.argv[4]
    
     
    
    # Set the env variables and use con function if mask is specified
    hp.SetEnvVar()
    if ThisMask != "#":
        hp.log("A Mask has been specified")

        
        dsc = arcpy.Describe(ThisMask)
        if not dsc.DatasetType == 'RasterDataset':

            hp.log("  Mask is not raster, converting to raster first")
            
            fields = arcpy.ListFields(ThisMask)
            # must get to an appropriate field first
            wipid = "NewId"
            hp.AddID(ThisMask, wipid)
            
        
            arcpy.env.extent = ThisMask
            arcpy.env.snapRaster = sys.argv[2]
            
            arcpy.PolygonToRaster_conversion(ThisMask, wipid, (os.path.join(hp.SWorkspace, "TempMask")),"MAXIMUM_AREA", "None", tempdem)
            TempMask = Raster(os.path.join(hp.SWorkspace, "TempMask"))
             
        else:
            TempMask = ThisMask
           
        Mask = Reclassify(TempMask, "VALUE", "0 1000000000000 1", "DATA")
        
        Input_DEM = Con(Mask, tempdem)
        
        
    else:
        Input_DEM = tempdem
  
    # Input_DEM now represents the area of interest, or mask. Find units from projection info
    dsc = arcpy.Describe(Input_DEM)
    sr = dsc.SpatialReference
    
    _sr = sr.exporttostring().split(',')
    for i, e in enumerate(_sr):
        print i, e
    if sr.Type != "Projected":
        hp.log(" These tools can not work unless the input datasets are projected,\n  Stopping execution")
        raise
    print " Projection name = %s\n Projection factory code = %s" % (sr.Name, sr.FactoryCode)
   
    hp.units['type'] = sr.linearUnitName
    hp.units['cellsqft'] = pow(dsc.MeanCellHeight * float(sr.exporttostring().split(',')[-1].split("]")[0]) / 0.30480060960121924, 2)
    hp.units['size'] = dsc.MeanCellHeight
    

    # Write out dataset properties
    print "Input DEM data type = %s, %s, %s" % (dsc.DatasetType, dsc.DataType, dsc.IsInteger)
    # Set the mask for use in later tools
    #~ arcpy.SaveSettings(os.path.join(hp.Workspace, "envSettings.xml"))
    mainMask = Reclassify(Input_DEM, "VALUE", "0 1000000000000 1; 0 NoData", "DATA")
    hp.Mask = SetNull(mainMask, mainMask, "VALUE = 0")
    #~ hp.Mask = Reclassify(mainMask, "VALUE", "0 NoData", "DATA") # The above step has a bug or missing Env var when run manually from the toolbox that prvents it functioning correctly without this step
    hp.saveRasterOutput(hp.Mask,"Mask")
    
    # Local variables...
    demxarea = os.path.join(hp.Workspace, "demxarea")

    #~ hp.log("Convert to ASCII...")
    
    
    hp.log("Fill DEM...")
    Filled_DEM = arcpy.sa.Fill(Input_DEM)
    hp.log("Calculate Flow Direction...")
    flowdir = FlowDirection(Filled_DEM, "NORMAL")* hp.Mask # NORMAL should be FORCE?
    
    hp.saveRasterOutput(flowdir,"flowdir")
    
    #~ flowdir = Output_flow_direction_raster * hp.Mask
    flowdir.save(os.path.join(hp.SWorkspace,"flowdir"))
    hp.Mask.save(os.path.join(hp.SWorkspace,"mask"))
    Flow_Acc = hp.BMP2DA(flowdir, "CumDa", hp.Mask)
    
    hp.log("Clip...")
    flow_accum = hp.Mask*Flow_Acc
    flow_accum.save(os.path.join(hp.Workspace + "\\WIPoutput.mdb", "flowacc"))
    if sys.argv[5] == '#':
        hp.log("Stream Calculation...")
        StreamThr = float(Threshold_for_stream_formation__acres_) * 43560 / hp.units["cellsqft"]
        print "    Finding cells with accumulation greater than %s" % StreamThr
        Stream_Raster = flow_accum > StreamThr
    else:
        Stream_Raster = Raster(sys.argv[5])
    
    hp.log("Remove background values...")
    Streams_Output_Raster = Reclassify(Stream_Raster, "VALUE", "0 NODATA;1 1","DATA")
    hp.saveRasterOutput(Streams_Output_Raster,"streams")
     
    hp.log("Vectorize streams...")
    
    Stream_Vector = os.path.join(hp.Workspace + "\\WIPoutput.mdb", "streamsvec")
    StreamToFeature(Streams_Output_Raster, flowdir, Stream_Vector, "SIMPLIFY")
    hp.models[hp.current_tool]["output"].append(Stream_Vector)
    
    hp.log("Drainage Area Calculation...")
    conv = hp.units['cellsqft'] / 43560
    Cumulative_Drainage__Flow_Acc__Output_Raster = flow_accum*conv
    hp.saveRasterOutput(Cumulative_Drainage__Flow_Acc__Output_Raster,"cumda")
    hp.Close()

except:       
    i, j, k = sys.exc_info()
    hp.EH(i, j, k)
    