# HAL

This folder contains all HAL implementations for embedded applications.
Applications should be able to include headers defined in [include/] and
then one of the implemations should be implemented and linked. All
implementations should implement the same api past some hardware-specific
initialization routine.

Board and chip definitions live in [platforms/boards/](../platforms/boards)
and [platforms/chips/](../platforms/chips). A HAL implementation should be
`target_compatible_with` the chip it supports.
