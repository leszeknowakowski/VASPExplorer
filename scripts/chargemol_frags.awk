#-------------------------------------------------------------------------------------
# An AWK script to correct the chargemol output to include atom labels and to calculate
# bonding effect (sum of bond orders) between defined fragments.
#
# awk -v [atom specifications] -v frag1=[list of atoms] -v frag2=[list of atoms] \
#     -f chargemol_cleanup_bo.awk DDEC6_even_tempered_bond_orders.xyz  > DDEC6_even_tempered_bond_orders-corrected.xyz
#
# format of the atom specification list (the same as in vasp_bader_correct.awk, however,
# the valencies are just ignored):
#    atom specifications should be separated by ";" or ","
#    within the specification: the range ("from"-"to") should be separated from
#       the valence and the symbol by colons (":").
#    The ranges MUST be mutually exclusive - no checking provided!
#
#    Fragment definition (frag1 and frag2) is defined as list (comma separated) of
#       atom indices or ranges (separated by "-").
#
# e.g.:
#   awk -v atoms="1-3:2:Co; 4-10:6:O"
#          which means that atoms 1-3 have valence 2 (Co ions)
#          and atoms 4-10 have valence 6 (O ions)
#       -v frag1="1,2,3,4,5,10-20" [-v frag2="6-9,21-40"]
#
#    If the second fragment is undefined, it is composed of all atoms not belonging to frag1.
#
#
#
# Written by Witold Piskorz, Krakow 2014, based on vasp_bader_correct.awk.
#
#  25.11.2014 - initial version; W.P.
#  26.11.2014 - cleanup; W.P.
#  27.11.2014 - ranges analysis of fragments definition added
#  27.11.2014 - ****** version 1.0 released
#  28.11.2014 - minor cleanup
#  18.03.2015 - adapted for lobster 1.2.0
#  10.01.2017 - adapted for Chargemol; requires conversion to .csv, see chargemol_frags.sh
#
# TODO: if no frag2 is set, assume all atoms but frag1
#  05.09.2023 - done; W.P.
#  05.09.2023 - ****** version 2.0 released
#
#-------------------------------------------------------------------------------------


function pretty_print_array(arr, arr_length){
    for(i = 1; i < arr_length+1; i++){
        printf("%s ", arr[i]) > error_log;
    }
}



function val_exists(arr, arr_length, value){
    for(i = 1; i < arr_length+1; i++){
        if(i in arr)
            if(arr[i] == value)
                return 1;
    }
    return 0;
}


BEGIN{
    integer_number = "[[:digit:]]+";

    outfile = "/dev/stdout";
    error_log = "/dev/stderr";

    OFS="\t"
    gsub(/\"/, "", atoms);  #remove quotation marks "
    split(atoms, atom_list, /[;,]/);


# 1st fragment: =============================
    k = 1;
    if(frag1 != ""){
        n = split(frag1, frag1_ranges, /[;,]/);
        printf("Fragment 1: %d range(s)/def(s) found:\n", n)  > error_log;
        for(i = 1; i < n+1; i++){
            printf(" range/def: %s\n", frag1_ranges[i])  > error_log;
            m = split(frag1_ranges[i], from_to_f1, /-/);
#this is range atom indices:
            if(m > 1){
                printf("   it is RANGE: %s\n", frag1_ranges[i])  > error_log;
                from = from_to_f1[1]+0; to = from_to_f1[2]+0;   #"+0" = enforcing decimal, cleaning up - removing trailing spaces etc.
                if(from > to){  # 'from' must be <= 'to'
                    tmp = from;  from = to;  to = tmp;
                }
                for(j = from; j < to+1; j++){
                    #printf("  index: %d\n", j)  > error_log;
                    frag1_arr[k++] = j;
                }
            } else {
#this is just atom index:
                printf("index found: %s\n", frag1_ranges[i])  > error_log;
                frag1_arr[k++]=frag1_ranges[i];
            }
        }
        frag1_length = k;
        printf("Complete fragment 1 definition:\n")  > error_log;
        pretty_print_array(frag1_arr, frag1_length);
        printf("\n\n")  > error_log;
    } else {
        printf("Note: no fragment 1 defined\n")   > error_log;
    }
    fflush(error_log);

# 2nd fragment: =============================
    k = 1;
    if(frag2 != ""){
        n = split(frag2, frag2_ranges, /[;,]/);
        printf("Fragment 2: %d range(s)/def(s) found:\n", n)  > error_log;
        for(i = 1; i < n+1; i++){
            printf(" range/def: %s\n", frag2_ranges[i])  > error_log;
            m = split(frag2_ranges[i], from_to_f2, /-/);
#this is range atom indices:
            if(m > 1){
                printf("   it is RANGE: %s\n", frag2_ranges[i])  > error_log;
                from = from_to_f2[1]+0; to = from_to_f2[2]+0;   #"+0" = enforcing decimal, cleaning up - removing trailing spaces etc.
                if(from > to){  # 'from' must be <= 'to'
                    tmp = from;  from = to;  to = tmp;
                }
                for(j = from; j < to+1; j++){
                    #printf("  index: %d\n", j)  > error_log;
                    frag2_arr[k++] = j;
                }
            } else {
#this is just atom index:
                printf("index found: %s\n", frag2_ranges[i])  > error_log;
                frag2_arr[k++]=frag2_ranges[i];
            }
        }
        frag2_length = k;
        printf("Complete fragment 2 definition:\n")  > error_log;
        pretty_print_array(frag2_arr, frag2_length);
        printf("\n\n")  > error_log;
    } else {
        printf("**** Note: frag2 is undefined so all atoms not present in frag1 count. ****\n\n")   > error_log;
    }




    first_atom = 1;
#fill the element symbol versus atom number array
    for (i in atom_list){
        r = split(atom_list[i], range_list, /:/); #range_list[1] has ranges, range_list[2] - valency, and range_list[3] - symbol
        split(range_list[1], from_to, /-/); #Range list = range_list[1]; Valence = range_list[2]
        valence = range_list[2];
        symbol = range_list[3];

        from = from_to[1]+0; to = from_to[2]+0;   #"+0" = enforcing decimal, cleaning up - removing trailing spaces etc.
        if(from > to){  # 'from' must be <= 'to'
            tmp = from;  from = to;  to = tmp;
        }

        printf("Processing range: %d-%d (%s)\n", from, to, symbol)   > error_log;
        for(j = from; j <= to; j++){
            atom_nr_symb[j] = symbol;
        }

#memorise the number of the last atom:
        if(last_atom < to)
            last_atom = to;
#memorise the number of the first atom (should be == 1...)
        if(first_atom > from)
            first_atom = from;
    }

    #printf("1st atom: %d, last atom: %d\n", first_atom, last_atom);


    printf("\n************ Processing Chargemole output file **************\n\n")   > error_log;

    sum_BO_a = 0;

    do {
        flag = getline; # < name;
        if($1 ~ /#/) {
            #print;
            getline;
        }

#lobster:
#  COOP#  atomMU  atomNU     distance          ICOOP(eF)  for spin  1
#      1       1      49      2.00568            0.09369

##Chargemole:
##Bond order values exceeding threshold value of 0
#Ni;  1;  Ni;  13;  0.0196
#Ni;  1;  Ni;  14;  0.0026
#Ni;  1;  Ni;  15;  0.3326

        gsub(/;/, "", $2);  #remove semicolon
        gsub(/;/, "", $4);  #remove semicolon
        atomMU = $2"("atom_nr_symb[$2]")";
        atomNU = $4"("atom_nr_symb[$4]")";

        #printf("% 7s % 7s % 7s%13.5f%19.5f\n", $1, atomMU, atomNU, $4, $5);
        #if(val_exists(frag1_arr, frag1_length, $2+0))
        #    printf("val %d exists in field 2\n", $2+0);
        #if(val_exists(frag1_arr, frag1_length, $4+0))
        #    printf("val %d exists in field 3\n", $4+0);

# If frag2 is defined
        if(frag2_length+0 > 0){
            if( (val_exists(frag1_arr, frag1_length, $2+0) && val_exists(frag2_arr, frag2_length, $4+0)) || \
                (val_exists(frag2_arr, frag2_length, $2+0) && val_exists(frag1_arr, frag1_length, $4+0)) \
            ) {
                printf("Indices %d and %d were FOUND and DID belong to different fragments:\n", $2+0, $4+0)   > error_log;
                ##printf("--> %s\n", $0)   > error_log;
                printf("  line: \"% 7s % 7s%19.5f\"\n", atomMU, atomNU, $5)  > error_log;
                sum_BO += $5;
            }
        } else {
# Here frag2 is undefined, i.e., all atoms not present in frag1 should be taken
            if( (val_exists(frag1_arr, frag1_length, $2+0) && ! val_exists(frag1_arr, frag1_length, $4+0)) || \
                (! val_exists(frag1_arr, frag1_length, $2+0) && val_exists(frag1_arr, frag1_length, $4+0)) \
            ) {
                printf("Indices %d and %d were FOUND and DID belong to different fragments (1st present and 2nd absent or vice versa):\n", $2+0, $4+0)   > error_log;
                ##printf("--> %s\n", $0)   > error_log;
                printf("  line: \"% 7s % 7s%19.5f\"\n", atomMU, atomNU, $5)  > error_log;
                sum_BO += $5;
            }
        }
    } while ((flag > 0));


    printf("sum_BO = %f\n", sum_BO)  > error_log;
}

