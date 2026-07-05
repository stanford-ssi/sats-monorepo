# HAL

This folder contains all HAL implementations for embedded applications.
Applications should be able to include headers defined in [include/] and
then one of the implemations should be implemented and linked. All
implementations should implement the same api past some hardware-specific
initialization routine.

[boards/]
Board hardware definitions should be defined in [boards/]. 
