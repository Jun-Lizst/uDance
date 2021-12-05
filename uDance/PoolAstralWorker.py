from os.path import join
from glob import glob
from pathlib import Path
from sys import stderr
import shutil
from subprocess import Popen, PIPE

from uDance.expand_dedupe_newick import expand_dedupe_newick


class PoolAstralWorker:
    options = None
    astral_exec = None

    @classmethod
    def set_class_attributes(cls, options, astral_exec):
        cls.options = options
        cls.astral_exec = astral_exec

    @classmethod
    def worker(cls, partition_output_dir):
        genes = glob(join(partition_output_dir, "*", ""))
        for gene in genes:
            if cls.options.method == 'iqtree':
                best = Path(join(gene, 'RUN.treefile'))
            elif cls.options.method == 'raxml-ng':
                best = Path(join(gene, 'RUN.raxml.bestTree'))
            elif cls.options.method == 'raxml-8':
                best = Path(join(gene, 'RAxML_bestTree.file'))
            bestCollapsed = Path(join(gene, 'RUN.raxml.bestTreeCollapsed'))
            if bestCollapsed.is_file():
                raxtree = bestCollapsed
            elif best.is_file():
                raxtree = best
            else:
                stderr.write("%s/RUN.raxml.bestTree does not exist. RAxML job is corrupted. \n" % gene)
                continue
            treestr = open(raxtree).readline()
            dupmap_file = Path(join(gene, "dupmap.txt"))
            if dupmap_file.is_file():
                dmp = list(map(lambda x: x.strip().split("\t"), open(dupmap_file).readlines()))
                expanded_tree_str = expand_dedupe_newick(treestr, dmp)
            else:
                expanded_tree_str = treestr
            with open(join(gene, "raxml.expanded.nwk"), "w") as out:
                out.write(expanded_tree_str)
        expanded_trees = glob(join(partition_output_dir, "*", "raxml.expanded.nwk"))
        astral_input_file = join(partition_output_dir, "astral_input.trees")

        with open(astral_input_file, 'wb') as wfd:
            for f in expanded_trees:
                with open(f, 'rb') as fd:
                    shutil.copyfileobj(fd, wfd)

        astral_output_file, astral_log_file, astral_const_file = [dict(), dict(), dict()]
        astral_const_file["incremental"] = join(partition_output_dir, "astral_constraint.nwk")
        astral_const_file["updates"] = join(partition_output_dir, "raxml_constraint.nwk")

        for mtd in ["incremental", "updates"]:
            astral_output_file[mtd] = join(partition_output_dir, "astral_output.%s.nwk" % mtd)
            astral_log_file[mtd] = join(partition_output_dir, "astral.%s.log" % mtd)
            s = ["java", "-Xmx%sG" % cls.options.memory, "-jar", cls.astral_exec, "-i", astral_input_file,
                 "-o", astral_output_file[mtd]]
            if Path(astral_const_file[mtd]).is_file():
                s += ["-j", astral_const_file[mtd]]
            with open(astral_log_file[mtd], "w") as lg:
                with Popen(s, stdout=PIPE, stdin=PIPE, stderr=lg) as p:
                    astral_stdout = p.stdout.read().decode('utf-8')
                    #print(astral_stdout)

        # if cls.options.use_gpu:
        #     gpu_opt = ""
        # else:
        #     gpu_opt = "-C"

        # s = f'cp {astral_const_file} {astral_output_file}\n'
        # s = ["cp", astral_const_file, astral_output_file]
