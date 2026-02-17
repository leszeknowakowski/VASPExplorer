#===================================================================================
#
# An AWK script to create the string with ranges for vasp_bader_correct.awk script.
# See vasp_bader_correct.awk for details
#
#  by Witold Piskorz, Krakow 10.04.2013
#
#  10.04.2013  - initial version; W.P.
#  10.06.2013  - added element symbol labels; W.P.
#  12.06.2013  - corrected bug (old vs. new POSCAR format); W.P.
#  06.11.2019  - corrected bug with flag handling; W.P.
#
#===================================================================================


BEGIN{
    outfile = "/dev/stdout";
    error_log = "/dev/stderr";
    poscar = "POSCAR";
    potcar = "POTCAR";
# pattern to match a real number
    real_number = "-?[[:digit:]]+\\.[[:digit:]]+";  #real number, i.e. optional minus, >0 decimal digits, dot, >0 decimal digits
    integer_number = "[[:digit:]]+";  #integer number, i.e. >0 decimal digits



    i = 0;
    do {
        flag = getline < poscar;
        i++;  #"getline < file" does not increment NR (as plain "getline" does)
    } while ((flag > 0) && i < 6);
    n_elements = i;
    if (flag <= 0) {
        print "Could not open "poscar"!" > error_log;
	print "Cannot continue!" > error_log;
        exit;
    }
#We can have either numbers of atoms (old VASP) or element symbols (new VASP)
    if($1 ~ integer_number){
        print "Old POSCAR format (w/o. symbols)"  > error_log;
        print "numbers of atoms: "$0  > error_log;
    } else {
        print "New POSCAR format (w. symbols)"  > error_log;
        print "element symbols: "$0  > error_log;
        getline < poscar;
        print "numbers of atoms: "$0  > error_log;
    }
#Now we have atom counts in either case
    n = split($0, atom_counts);

#Now search POTCAR for values of ZVAL
    i = 1;
    do {
        flag = getline < potcar;
        if($1 ~ /TITEL/){
            symbol[i] = $4;
        }
        if($1 ~ /POMASS/ && $4 ~ /ZVAL/){
            zval[i] = $6;
            print i"; valence: "zval[i]"; symbol: "symbol[i]  > error_log;
            i++;
        }
    } while ((flag > 0));
    if (flag < 0) {
        print "*********************************************"  > error_log;
        print "Could not open "potcar", error code = "flag"."  > error_log;
        print "Element symbols will not be printed."  > error_log;
        print "*********************************************"  > error_log;
    } else {
        print potcar" file read successfully."  > error_log;
    }


#Construct the line with ranges
    prev = 0;
    for(i = 1; i < n+1; i++){
        curr = atom_counts[i]+prev;
        print prev+1"-"curr":"zval[i]":"symbol[i]  > error_log;
        line = line""sprintf("%s, ", prev+1"-"curr":"zval[i]":"symbol[i]);
        prev = curr;
    }

#Trim the trailing ", "
    line = substr(line, 0, length(line)-2);
    print line;
}
