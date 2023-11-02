#!/bin/bash

# Find all Python files and .env files in the app directory and its subdirectories
files=$(find ../app -name "*.py" -o -name ".env")

# Process each file
for file in $files; do
    if [[ $file == *.py ]]; then
        # For Python files: format with black and isort
        black $file
        isort $file
    elif [[ $file == *.env ]]; then
        # For .env files: remove trailing whitespaces
        sed -i 's/[[:space:]]*$//' $file
    fi
done
