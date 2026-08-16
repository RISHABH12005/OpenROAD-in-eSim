# OpenROAD in Ubuntu 22.04.5

## Test-1
```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y build-essential cmake git clang bison flex tcl-dev libffi-dev libreadline-dev zlib1g-dev python3 python3-pip python3-venv swig qtbase5-dev libboost-all-dev

sudo apt install -y libx11-dev libxaw7-dev libxmu-dev libxext-dev libglu1-mesa-dev libeigen3-dev
```

## Test-2
```bash
sudo apt install -y \
  build-essential clang cmake git swig \
  tcl-dev tk-dev \
  bison flex \
  libreadline-dev \
  zlib1g-dev \
  libboost-all-dev \
  libeigen3-dev \
  python3 python3-pip \
  libglu1-mesa-dev freeglut3-dev mesa-common-dev \
  libx11-dev libxext-dev libxrender-dev libxrandr-dev libxinerama-dev libxcursor-dev \
  libcurl4-openssl-dev \
  g++ libstdc++-12-dev libc++-dev libc++abi-dev \
  qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools \
  libxcb-cursor0 libxcb-xinerama0 libxcb-xkb1 \
  libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-render-util0 \
  libre2-dev

sudo apt install -y npm
sudo npm install -g @bazel/bazelisk

bazelisk version

cd ~
git clone --recursive https://github.com/The-OpenROAD-Project/OpenROAD.git
cd OpenROAD

bazelisk clean --expunge
rm -rf ~/.cache/bazel

bazelisk build --//:platform=gui //:openroad --jobs=4

./bazel-bin/openroad         # for CLI Mode
help
exit

./bazel-bin/openroad -gui    # for GUI Mode

sudo apt install -y libxcb-cursor0

sudo apt install -y \
  libxcb-xinerama0 libxcb-xkb1 \
  libxkbcommon-x11-0 libxcb-icccm4 \
  libxcb-image0 libxcb-keysyms1 \
  libxcb-render-util0
```