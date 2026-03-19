# msr-cli
### 下载明日方舟塞壬唱片官网的歌曲
### 已实现功能：搜索，下载，批量下载，一键下载全部，自动转flac
## 安装依赖
`python -m pip install rich requests`
## 使用
1. 获取帮助 `python msr_cli.py --help`
2. 列出所有专辑 `python msr_cli.py list`
3. 搜索 `python msr_cli.py search 春弦`
4. 通过ID下载专辑 `python msr_cli.py album --id 6678`
5. 直接通过专辑名下载专辑 `python msr_cli.py album 铁花飞`
6. 下载专辑并转为FLAC `python msr_cli.py album --id 6678 --flac`
7. 批量下载专辑 `python msr_cli.py album --ids 6678,4527,1038`
8. 一键下载全部 `python msr_cli.py all`

## 保存说明
### 会自动将歌曲文件、对应歌词（如果有）、封面图片和简介文本按专辑名称分别保存在当前目录的“downloads”文件夹（默认情况），可以使用`--path`参数指定保存路径

## 截图示例
<img width="1978" height="1186" alt="image" src="https://github.com/user-attachments/assets/56e04a08-00be-4ead-8614-3a129e1e395a" />
<img width="1978" height="1186" alt="image" src="https://github.com/user-attachments/assets/9b8a0746-ea7f-4741-9a6f-8c7ea33b3a3c" />
