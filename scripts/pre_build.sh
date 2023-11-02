#!/bin/bash

# Find all Python files in the app directory and its subdirectories
files=$(find ../app -name "*.py")

# Run black and isort on each file
for file in $files; do
    black $file
    isort $file
done