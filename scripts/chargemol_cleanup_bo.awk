#-----------------------------------------------------------------------------------
#
#  AWK script to cleanup chargemol's bond order output.
#  usage: awk -f cleanup_chargemol_bo.awk \
#         [-v threshold=value] \
#         [-v format="csv"] \
#         [-v triangle="yes"] \
#         < DDEC6_even_tempered_bond_orders.xyz > DDEC6_even_tempered_bond_orders.csv
#
#
#  by Witold Piskorz; Kraków 22.11.2016.
#    initial version;                                      22.11.2016
#    CSV format support;                                   23.11.2016
#  FIXME: remove redundancy (BO matrix is symmetric).
#    FIXED: "triangle" flag (default = yes) prints out
#           only upper triangle                            24.11.2016
#    adapted to chargemol version 3.5                      21.09.2018
#
#-----------------------------------------------------------------------------------




BEGIN {
    if(threshold == ""){
        threshold = 0.1;
    }
    print "#Bond order values exceeding threshold value of "threshold;
    if(triangle == ""){
        triangle = "yes";
        print "#Note: only uppper triangular matrix elements are printed";
    }
    if(tolower(format) == "csv"){
        print "Format CSV selected."   > "/dev/stderr";
    } else {
        print "Free format selected."   > "/dev/stderr";
    }
}



/Printing [E]?BOs for ATOM \#/ {
    atom1_nr = $6
    atom1_sym = $8;
    start = 1;
    at1[atom1_nr] = atom1_sym;
}


/The sum of bond orders for this atom is SBO =/ {
    start = 0;
}



#Bonded to the (  1,   0,   0) translated image of atom number    57 ( O  ) with bond order =     0.0142
(start == 1 && $1 == "Bonded") {
    atom2_nr = $13;
    atom2_sym = $15;
    bo = $21;

#print only one triangle of the BO matrix (if requested):
    if(tolower(triangle) == "yes" && (atom1_nr > atom2_nr) ){
        ;
    } else {
        if(bo >= threshold) {
            if(tolower(format) == "csv"){
                print atom1_sym";  "atom1_nr";  "atom2_sym";  "atom2_nr";  "bo;
            } else {
                print atom1_sym"("atom1_nr")-"atom2_sym"("atom2_nr"): "bo;
            }
        }
    }
}

