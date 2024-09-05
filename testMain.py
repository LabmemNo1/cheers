import subprocess
import os

def saveTerminalOutput(command, output_file):
    with open(output_file,'w') as f:
        try:
        #运行命令并捕获输出
            output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
            #将输出写入文件
            f.write(output)
        except subprocess.CalledProcessError as e:
        #如果命令返回非等状态码，将错误信息写入女件
            f.write(e.output)

currentFilePath = __file__
logPath = os.path.dirname(currentFilePath) + '\\log.txt'
print("1")

# if(os.path.exists(logPath) == False):
#     os.mkdir(logPath)

command = 'C:/Users/Mao/AppData/Local/Programs/Python/Python39/python.exe h:/dnfm/Cheers/main.py'
saveTerminalOutput(command, logPath)