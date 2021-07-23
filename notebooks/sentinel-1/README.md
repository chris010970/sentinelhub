# sentinelhub
Demonstration of multi-faceted capabilities of [Sentinel Hub](https://www.sentinel-hub.com/) in Python development environment - includes implementation of [Process API](https://docs.sentinel-hub.com/api/latest/api/process/) client linked with functionality of the Singerise [sentinelhub-py] (https://sentinelhub-py.readthedocs.io/en/latest/) Python package.

[Sentinel Hub](https://www.sentinel-hub.com/) is a multi-spectral and multi-temporal big data satellite imagery service, capable of fully automated archiving, real-time processing and distribution of remote sensing data and related EO products. Leveraging Sentinel-Hub APIs, users may programmatically retrieve satellite imagery satisfying customisable spatial and temporal constraints from ESA Data and Information Access Service (DIAS) servers in a matter of seconds.

Repository contents:
* [src](https://github.com/chris010970/sentinelhub/tree/main/src) : Process API client-side source code - implements on-the-fly georeferencing and visualisation functionality
* [notebooks](https://github.com/chris010970/sentinelhub/tree/main/notebooks): Example Jupyter notebooks demonstrating functionality of Python Process API client to extract, download, analyse and visualise various Open Earth Observation datasets
* [cfg](https://github.com/chris010970/sentinelhub/tree/main/cfg) :  Client API configuration files utilised within Jupyter notebooks 

Sentinel-Hub Process API provides a human readable RESTful API interface to traditional OGC WFS, WMS and WCS protocols. To implement customisable product processing, JavaScript program code forwarded via body of HTTPS requests is executed on-the-fly by Sentinel-Hub web services. Encoded in YAML format, configuration files include 
product evaluation code based on custom scripts taken from [Sentinel-Hub examples repository](https://custom-scripts.sentinel-hub.com/) and [Sentinel-Hub Process API documentation](https://docs.sentinel-hub.com/api/latest/api/process/). 

Example Sentinel-Hub custom scripts may be interactively evaluated in [EO Browser](https://apps.sentinel-hub.com/eo-browser) and [Sentinel Playground](https://apps.sentinel-hub.com/sentinel-playground/) browser applications.

Collections of demonstration Jupyter notebooks:
* [Sentinel-1](https://github.com/chris010970/sentinelhub/tree/main/notebooks/sentinel-1/README.md)
* [Sentinel-2](https://github.com/chris010970/sentinelhub/tree/main/notebooks/sentinel-2/README.md)
* [Sentinel-3](https://github.com/chris010970/sentinelhub/tree/main/notebooks/sentinel-3/README.md)
* [EOS MODIS](https://github.com/chris010970/sentinelhub/tree/main/notebooks/modis/README.md)
* [Landsat-8](https://github.com/chris010970/sentinelhub/tree/main/notebooks/landsat-8/README.md)
