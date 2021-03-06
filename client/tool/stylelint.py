#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# Copyright (c) 2021-2022 THL A29 Limited
#
# This source code file is made available under MIT License
# See LICENSE for details
# ==============================================================================

"""
Stylelint: css style static analyzer
"""

import os
import sys
import json
import codecs
from shutil import copyfile

from task.scmmgr import SCMMgr
from task.codelintmodel import CodeLintModel
from util.exceptions import AnalyzeTaskError
from util.configlib import ConfigReader
from util.subprocc import SubProcController
from util.pathfilter import FilterPathUtil
from util.logutil import LogPrinter
from util.textutil import StringMgr


class Stylelint(CodeLintModel):
    def __init__(self, params):
        CodeLintModel.__init__(self, params)
        self.sensitive_word_maps = {"Stylelint": "Tool", "stylelint": "Tool"}

    def analyze(self, params):
        """

        :param params:
        :return:
        """
        source_dir = params.source_dir
        work_dir = os.getcwd()
        rules = params.rules
        envs = os.environ
        incr_scan = params["incr_scan"]
        path_exclude = params.path_filters.get("exclusion", [])
        error_output = os.path.join(work_dir, "styleliint-output.txt")

        if os.environ.get("STYLELINT_MAX_OLD_SPACE_SIZE", None):
            scan_cmd = ["node", "--max-old-space-size=" + os.environ.get("STYLELINT_MAX_OLD_SPACE_SIZE")]
            if sys.platform == "win32":
                scan_cmd.append(
                    os.path.join(os.environ.get("NODE_HOME"), "node_modules", "stylelint", "bin", "stylelint.js")
                )
            else:
                scan_cmd.append(
                    os.path.join(os.environ.get("NODE_HOME"), "lib", "node_modules", "stylelint", "bin", "stylelint.js")
                )
        else:
            scan_cmd = ["stylelint"]
        scan_cmd.extend(["--allow-empty-input", "--ignore-disables"])

        config_file = self.config(params)
        if config_file:
            scan_cmd.extend(["--config", config_file])

        if "STYLELINT_SYNTAX" in envs:
            # ????????????????????????CSS???????????????Specify a non-standard syntax. Options: "scss", "sass", "less", "sugarss"
            scan_cmd.extend(["--syntax", envs.get("STYLELINT_SYNTAX")])

        if "STYLELINT_CUSTOM_SYNTAX" in envs:
            # Module name or path to a JS file exporting a PostCSS-compatible syntax.
            scan_cmd.extend(["--custom-syntax", envs.get("STYLELINT_CUSTOM_SYNTAX")])

        # ???????????????????????????????????????????????????????????????
        # ???????????????????????????????????????????????????
        toscans = []
        want_suffix = [".css", ".less", ".scss", "sass", ".sss"]
        global_files = '"**/*.{css, less, scss, sass, sss}"'
        if incr_scan:
            diffs = SCMMgr(params).get_scm_diff()
            toscans = [
                os.path.join(source_dir, diff.path).replace(os.sep, "/")
                for diff in diffs
                if diff.path.endswith(tuple(want_suffix)) and diff.state != "del"
            ]
            relpos = len(source_dir) + 1
            toscans = FilterPathUtil(params).get_include_files(toscans, relpos)

            # windows?????????????????????????????????????????????????????????soucedir????????????????????????
            # ?????? windows ?????????subprocess.Popen?????????shell=False????????????????????????????????????32768??????
            # ?????????????????????????????????32500???????????????????????????cppcheck???????????????
            if sys.platform == "win32" and len(" ".join(toscans)) > 32500:
                toscans = [global_files]
        else:
            toscans = [global_files]

        if not toscans:
            LogPrinter.debug("To-be-scanned files is empty ")
            return []

        scan_cmd.extend(toscans)

        # exclusion
        # ??????node-v12.16.3???stylelint --ignore-pattern?????????????????????????????????????????????
        exclu_path_arr = []
        if path_exclude:
            for tmp_path in path_exclude:
                exclu_path_arr.append("--ignore-pattern")
                exclu_path_arr.append('"' + tmp_path + '"')
        scan_cmd.extend(exclu_path_arr)

        self.print_log("scan_cmd: %s" % " ".join(scan_cmd))
        SubProcController(
            scan_cmd, stdout_filepath=error_output, cwd=source_dir, stderr_line_callback=self._cmd_callback
        ).wait()

        issues = []
        self._result_handle(issues, error_output, rules)
        LogPrinter.debug(issues)
        return issues

    def _cmd_callback(self, line):
        """
        ????????????log??????
        :param line: log
        :return:
        """
        self.print_log(line)
        if line.find("JavaScript heap out of memory") != -1:
            raise AnalyzeTaskError("Js????????????????????????????????????STYLELINT_MAX_OLD_SPACE_SIZE")
        elif line.find("RangeError: Invalid string length") != -1:
            raise AnalyzeTaskError("?????????????????????????????????Js???buffer.constants.MAX_STRING_LENGTH?????????????????????????????????????????????????????????????????????")

    def config(self, params):
        """
        ??????stylelint???????????????
        :param params:
        :return:
        """
        work_dir = params.work_dir
        envs = os.environ
        rules = params.rules
        config_path = None

        stylelint_config = envs.get("STYLELINT_CONFIG", None)
        stylelint_config_type = envs.get("STYLELINT_CONFIG_TYPE", None)

        if stylelint_config:
            LogPrinter.info("????????????????????????????????????????????????")
            config_path = stylelint_config
            return config_path

        # default custom tencent
        if stylelint_config_type not in ("default", "custom", None):
            LogPrinter.info("??????" + stylelint_config_type + "??????????????????????????????")
            config_file = "%s_stylelintrc.json" % (stylelint_config_type)
            config_path = os.path.join(work_dir, config_file)
            copyfile(os.path.join(envs.get("NODE_HOME"), config_file), config_path)
            return config_path

        if stylelint_config_type == "custom":
            self.print_log("?????????????????????stylelint????????????????????????????????????????????????")
            return config_path

        if stylelint_config_type == "default":
            pass

        LogPrinter.info("???????????????AlloyTeam??????????????????????????????")
        config_path = os.path.join(work_dir, "stylelintrc.json")
        copyfile(os.path.join(envs.get("NODE_HOME"), "stylelintrc.json"), config_path)
        # ??????????????????
        self._set_stylelint_rule(params, config_path, rules)

        return config_path

    def _set_stylelint_rule(self, params, config_file, rules):
        """
        ???????????????????????????
        :param params:
        :param config_file:
        :param rules:
        :return:
        """
        rule_list = params["rule_list"]
        with open(config_file, "r") as f:
            configContent = f.read()
            configContentJson = json.loads(configContent)
            configRules = configContentJson["rules"]

        if rules:
            for rule in configRules:
                if rule not in rules:
                    configRules[rule] = None

        # enable rules
        if rule_list:
            for rule in rule_list:
                rule_name = rule["name"]
                if rule_name not in configRules:
                    configRules[rule_name] = True
                # 2020-12-14 ????????????????????????
                if not rule["params"]:
                    continue
                param = rule["params"]
                try:
                    # 1. ???????????????????????????Json????????????
                    configRules[rule_name] = json.loads(param)
                except json.JSONDecodeError as e:
                    # 2. ??????key-value??????
                    # ?????????????????????????????????options??????
                    # demo: options=always
                    if "[stylelint]" in param:
                        rule_params = param
                    else:
                        rule_params = "[stylelint]\r\n" + param
                    rule_params_dict = ConfigReader(cfg_string=rule_params).read("stylelint")

                    if rule_params_dict.get("options"):
                        option = StringMgr.trans_type(rule_params_dict["options"])
                        rule_params = option
                        configRules[rule_name] = rule_params

        with codecs.open(config_file, "w", encoding="utf-8") as f:
            json.dump(configContentJson, f, ensure_ascii=False)

    def _result_handle(self, issues, error_output, rules):
        """
        ??????????????????
        :param issues:
        :param error_output:
        :param rules:
        :return:
        """
        if not os.path.exists(error_output) or os.stat(error_output).st_size == 0:
            LogPrinter.info("result is empty")
            return
        error_file = open(error_output, encoding="utf-8")
        for error in error_file.readlines():
            error = error[0:-1]  # ?????????????????????
            tmp = error.split()
            LogPrinter.info(error)
            LogPrinter.info(tmp)
            path = ""
            # ???????????? ???????????????????????????????????????????????????
            if error.endswith(".css") or error.endswith(".scss"):
                path = error
            elif len(tmp) > 1:
                location = tmp[0].split(":")
                line = int(location[0])
                column = int(location[1])
                msg = " ".join(tmp[2:-1])
                rule = tmp[-1]
                if rule not in rules:
                    continue
                if not path:
                    continue
                issues.append({"path": path, "rule": rule, "msg": msg, "line": line, "column": column})


tool = Stylelint

if __name__ == "__main__":
    pass
