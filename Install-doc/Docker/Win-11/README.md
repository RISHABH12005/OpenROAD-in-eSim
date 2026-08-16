# OpenROAD in Docker by WSL Integration 
## Power Shell Script

- Install docker 

- Enable the wsl2
  - Or by Manualy do
    ```bash
    wsl --install
    ```

- Go to Settings -> Resources -> WSL Integration-> Enable

- set up RAM & CPU the Docker
  - win + R
    - notepad    
  - Creat name in C:\Users\risha\.wslconfig
    - .wslconfig  

- All these is writem in the notepad
  ```
    [wsl2]
    memory=13GB
    processors=6
    swap=32GB
  ```

- Note
  - shutdown the wsl
    ```bash
      wsl --shutdown
    ```

  - open wsl
    ```bash
      wsl 
    ```    

  - info of RAM, CPU, Swap
    ```bash
      free -h 
    ```  
-
```bash
wsl --install -d Ubuntu-22.04
```

- for the default 
  ```bash
  wsl --set-default Ubuntu-22.04 
  ```

- uninstall 
  ```bash
  wsl --unregister Ubuntu-24.04
  ```
-
```bash
sudo apt-get update && sudo apt-get upgrade -y
```

- Running process see
  ```bash
    wsl -l -v  
  ```
-
```bash
sudo apt install ubuntu-desktop -y

gnome-session

git clone --recursive https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts 

cd D:\esim\OpenROAD-flow-scripts

./build_openroad.sh

wsl

cd flow

ls util
```