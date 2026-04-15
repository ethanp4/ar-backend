## Prepare
### Download model
Download the model from https://huggingface.co/depth-anything/Depth-Anything-V2-Large/blob/main/depth_anything_v2_vitl.pth and place in root of project

use python 3.13

### Create virtual environment
```python -m venv .\venv```

#### Enter virtual environment
Run `.\venv\Scripts\activate`<br>
Ensure that the prompt changed to show that youre in the virtual environment

#### Install packages to the virtual environment
```pip install -r requirements.txt```<br>
on windows run
```
pip uninstall -y torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

## Run
Start ```python .\receive_image.py```<br>
Once its ready then start `.\send_image.py` in a separate terminal<br>
Make sure you run the script while within the virtual environment so that dependencies are available
