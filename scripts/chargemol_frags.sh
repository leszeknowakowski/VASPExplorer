#!/bin/sh

echo "Note: POSCAR must have atom symbols as in CONTCAR." > /dev/stderr

#Examples:
#
# awk -v atoms="\"`awk -f ~/awk/vasp_bader_get_ranges.awk`\"" \
#     -v frag1="1,2,3,4,5-7,8,9,10,11-20" \
#     -v frag2="100-110" \
#     -f ~/awk/chargemol_frags.awk  DDEC6_even_tempered_bond_orders.xyz

#     -v frag1="1-125"   \ #Ni
#     -v frag2="126-143" \ #naphthalene

base_dir=$1
base_name="DDEC6_even_tempered_bond_orders"
script_dir="__SCRIPT_DIR__"


if [ ! -r "${base_dir}/${base_name}.xyz" ]; then
    echo "Cannot read file ${base_name}.xyz"
    echo "Were the DDEC calculations performed?"
    exit 1
fi

threshold=0
echo "Filtering the bond orders with threshold = $threshold."
awk -f "${script_dir}/chargemol_cleanup_bo.awk" \
         -v threshold=$threshold \
         -v format="csv" \
         -v triangle="yes" \
         < "${base_dir}/${base_name}.xyz" > "${base_dir}/${base_name}.csv"

echo "Summing up bond orders for requested fragments."
awk -v atoms="\"`awk -f "${script_dir}/vasp_bader_get_ranges.awk"`\"" \
    -v frag1="__FRAG1__" \
    __FRAG2_LINE__
    -f "${script_dir}/chargemol_frags.awk"  "${base_dir}/${base_name}.csv" \
    >  "${base_dir}/${base_name}-corrected.xyz" \
    2> "${base_dir}/${base_name}-fragments.xyz"

