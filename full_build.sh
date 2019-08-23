find . -path "./.pyenv" -prune -o -path "./pp/oppai-ng" -prune -o -type f \( -iname "*.c" -o -iname "*.o" -o -iname "*.so" \) -print -exec rm {} +
python3 setup.py build_ext --inplace