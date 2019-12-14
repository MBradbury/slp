from data.table.data_formatter import TableDataFormatter as BaseTableDataFormatter, ShortTableDataFormatter

class TableDataFormatter(BaseTableDataFormatter):
    def __init__(self):
        super().__init__()

    def format_value(self, name, value):
        if isinstance(value, dict) and 'mean' in value:
            
            #if name == "captured":
            #    return f"$\\arraycolsep=1.4pt\\begin{{array}}{{S S}}{value['mean']:.3f} & \\pm{value['ci95']:.3f} \\\\ {value['std']:.3f} & {value['sem']:.3f}\\end{{array}}$"
            #else:
            #    return f"$\\arraycolsep=1.4pt\\begin{{array}}{{S S}}{value['mean']:.2f} & \\pm{value['ci95']:.2f} \\\\ {value['std']:.2f} & {value['sem']:.2f}\\end{{array}}$"

            #return f"$\\arraycolsep=1.4pt\\begin{{array}}{{r}}{value['mean']:.2f} \\\\ \\pm{value['ci95']:.2f}\\end{{array}}$"

            if name == "normal latency" or name == "norm(sent,time taken)" or name == "attacker distance":
                return f"{value['mean']:.0f} $\\pm$ {value['ci95']:.0f}"

            elif name == "received ratio":
                return f"{value['mean']:.0f} $\\pm$ {value['ci95']:.1f}"

            elif name == "time taken":
                return f"{value['mean']:.1f} $\\pm$ {value['ci95']:.1f}"

            else:
                return f"{value['mean']:.1f} $\\pm$ {value['ci95']:.1f}"
        else:
            return super().format_value(name, value)

class ShortTableDataFormatter(ShortTableDataFormatter, TableDataFormatter):
    def __init__(self):
        super().__init__()
