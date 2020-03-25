import json
import os
import re
import subprocess
import urllib
from subprocess import PIPE

import ipykernel
from IPython import get_ipython
from IPython.core import page
from IPython.core.magic import register_line_magic
from IPython.display import Javascript
from mypy import api
from notebook import notebookapp

__author__ = "shiba6v"
__license__ = "MIT"

# https://stackoverflow.com/questions/12544056/how-do-i-get-the-current-ipython-jupyter-notebook-name


def notebook_path():
    """Returns the absolute path of the Notebook or None if it cannot be determined
    NOTE: works only when the security is token-based or there is also no password
    """
    connection_file = os.path.basename(ipykernel.get_connection_file())
    kernel_id = connection_file.split('-', 1)[1].split('.')[0]

    for srv in notebookapp.list_running_servers():
        # No token and no password, ahem...
        if srv['token'] == '' and not srv['password']:
            req = urllib.request.urlopen(srv['url']+'api/sessions')
        else:
            req = urllib.request.urlopen(
                srv['url']+'api/sessions?token='+srv['token'])
        sessions = json.load(req)
        for sess in sessions:
            if sess['kernel']['id'] == kernel_id:
                return os.path.join(srv['notebook_dir'], sess['notebook']['path'])
    return None


LINE_NUMBER_PATTERN = re.compile(r"# In\[(\d*)\]:")


def create_cell_table(code):
    # その行の時点で最後に実行されたセル番号
    last_cell_number = 0
    last_cell_number_table = []
    # 最後に実行されたセルからの行,セルカウント
    line_count_from_executed = 0
    cell_count_from_executed = 0
    count_from_executed_table = []
    is_exact_cell = True
    for i_line, l in enumerate(code.splitlines()):
        #         print(l)
        if l[:5] == "# In[":
            match = LINE_NUMBER_PATTERN.match(l)
            if match:
                # executed cell like: In[1]
                last_cell_number = int(match.group(1))
#                 print("match", match, match.group(1))
                line_count_from_executed = 0
                cell_count_from_executed = 0
            else:
                # not executed cell like: In[ ]
                line_count_from_executed = 0
                cell_count_from_executed += 1
#                 print("not match")
        line_count_from_executed += 1
#         print(l, line_count_from_executed)
        last_cell_number_table.append(last_cell_number)
        count_from_executed_table.append(
            (line_count_from_executed, cell_count_from_executed))
    return last_cell_number_table, count_from_executed_table


RESULT_NUMBER_PATTERN = re.compile(r"<string>:(\d*):")


def modify_result(result, last_cell_number_table, count_from_executed_table):
    new_result = []
    for l in result.splitlines():
        match = RESULT_NUMBER_PATTERN.match(l)
        if match:
            i_line = int(match.group(1))
            OFFSET = 4
            message = f"{str(count_from_executed_table[i_line][1])+' below from ' if count_from_executed_table[i_line][1]!=0 else '' }In [{last_cell_number_table[i_line]}]: line:{count_from_executed_table[i_line][0]-OFFSET}"
            new_l = RESULT_NUMBER_PATTERN.sub(message, l)
            new_result.append(new_l)
        else:
            new_result.append(l)
    return "\n".join(new_result)


@register_line_magic
def mypy(line):
    #     display(Javascript("IPython.notebook.save_notebook();"))
    nb = notebook_path()
    ret = subprocess.run(
        f"jupyter nbconvert --to python {nb} --stdout".split(" "), stdout=PIPE, stderr=PIPE)
    code = ret.stdout.decode('UTF-8')
    # suppress warning like <string>:110: error: Name 'get_ipython' is not defined
    code = "from IPython import get_ipython\n"+code
    last_cell_number_table, count_from_executed_table = create_cell_table(code)
#     print(code)
#     print(last_cell_number_table)
#     print(count_from_executed_table)
    result = api.run(['--ignore-missing-imports', '-c', code] + line.split())
    result = modify_result(
        result[0]+"\n"+result[1], last_cell_number_table, count_from_executed_table)
    page.page(result)
