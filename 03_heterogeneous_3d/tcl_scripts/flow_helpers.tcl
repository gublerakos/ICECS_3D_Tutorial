# Load the two tier views into the virtual 2D technology.
proc read_libraries {} {
  global tech_lef std_cell_lef extra_lef liberty_file extra_liberty
  read_lef $tech_lef
  read_lef $std_cell_lef
  read_lef $extra_lef
  read_liberty $liberty_file
  read_liberty $extra_liberty
}
