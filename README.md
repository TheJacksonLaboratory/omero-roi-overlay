# Project description
TMA (tissue micro array) can punch set sizes of circles from tissue that has been H&E imaged. Pathologist defines the ROI circles to be punched, needs to export images with the circle overlayed so the TMA technician can easily enter them into the TMA software.

# Solution
1. Upload images to OMERO
2. Draw ROIs of set sizes in QuPath and transfer back to OMERO
3. Run OMERO ROI_Overlay_Export script to attach and download a reduced-resolution PNG or JPEG image with the ROIs