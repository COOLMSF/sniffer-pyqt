import re

# Define the regular expression pattern to match txt file names
pattern = r"\.txt$"


data = "aaa.txt is not valid"
# Filter the file names in the network package directory using the regular expression pattern
txt_files = [ data for d in data if re.search(pattern, d) ]

# Print the filtered txt file names
print(txt_files)


