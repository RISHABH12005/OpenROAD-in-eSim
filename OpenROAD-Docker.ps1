# Power Shell Script

Install docker 

Enable the wsl2
     or
# Manualy do
  wsl --install

Go to Settings -> Resources -> WSL Intrigation -> Enable

# set up RAM & CPU the Docker
  # win + R
    notepad    
  # Creat name in C:\Users\risha\.wslconfig
    .wslconfig  

# all thins is writem in the notpad

  [wsl2]
  memory=13GB
  processors=6
  swap=32GB

# ----
  # shutdown the wsl
    wsl --shutdown

  # open wsl
    wsl   

  # info of RAM, CPU, Swap
    free -h 

# ----

wsl --install -d Ubuntu-22.04

# for the default 
  wsl --set-default Ubuntu-22.04 

# uninstall 
  wsl --unregister Ubuntu-24.04

sudo apt-get update && sudo apt-get upgrade -y

# Running process see
  wsl -l -v  

sudo apt install ubuntu-desktop -y

gnome-session

git clone --recursive https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts 

cd D:\esim\OpenROAD-flow-scripts

./build_openroad.sh

wsl

cd flow

ls util
