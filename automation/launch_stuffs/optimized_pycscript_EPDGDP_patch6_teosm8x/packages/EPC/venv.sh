#!/bin/bash
echo -e "\nChecking if virtualenv package present in system"
res=$(pip list | grep virtualenv)
if [[ $res == *virtualenv* ]]; then
        echo -e "Already virtualenv installed. Using the same version"
else
        echo -e "Virtenv doesnt exist. Installing now"
        sudo pip3 install --no-index --find-links=../pre_packages/virt/ virtualenv
fi

echo -e "\nCleaning the old repositories"
./clean.sh

echo -e "\nStep -2 : Create the virtual environment"
virtualenv --python=/usr/bin/python3 --never-download --extra-search-dir=../pre_packages/ virtenv

echo -e "\nStep -3:  Activating the virtual environment"
source virtenv/bin/activate

echo -e "\nStep -4: Install the requirements"
pip install --no-index --find-links=../packages/ -r requirements.txt

echo -e "\nStep -5: Removing the trailing spaces from cfg file"
sed -i 's/[[:space:]]*$//' lte_epc.cfg

echo -e "\nStep -6: Run the code"

while read -r key value
  do
    if [ "$key" == "SGW_TOTAL_NUM_NODES_CP_AND_DP" ] ; then
	    #export num_sgw_dp=$(echo $value-2 | tr -d $'\r' | bc)
	    sgw_nodes=$(echo $value-2 | tr -d $'\r' | bc)
    fi
    if [ "$key" == "PGW_TOTAL_NUM_NODES_CP_AND_DP" ] ; then
	    #export num_pgw_dp=$(echo $value-2 | tr -d $'\r' | bc)
	    pgw_nodes=$(echo $value-2 | tr -d $'\r' | bc)
    fi
    if [ "$key" == "EPC_CONTEXT_NAME" ]; then
	    #export CONTEXT=$(echo $value | tr -d $'\r')
	    context=$(echo $value | tr -d $'\r')
    fi
  done < 'lte_epc.cfg'

export num_sgw_dp=$sgw_nodes
export num_pgw_dp=$pgw_nodes
export CONTEXT=$context
  
export nsd_name=$1
echo $nsd_name
python code.py

echo -e "\nStep -7: Deactivate the venv"
deactivate

echo -e "\nStep -8: Removing the virtenv directory"
rm -rf virtenv
