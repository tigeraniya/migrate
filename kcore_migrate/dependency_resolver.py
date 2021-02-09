
class N:
    def __init__(self,name,depends_on=[]):
        self.name = name
        self.depends_on = depends_on

def dependency_graph(inputs):
    g = {}
    for i in inputs:
        assert i.name not in g
        g[i.name] = set(i.depends_on)
    return g

def get_no_dep_nodes(deps):
    no_deps = set()
    for i in deps:
        if not deps[i]:
            no_deps.add(i)
    return no_deps


def transfer(iset,rset,olist):
    for r in rset:
        if r in iset:
            iset.remove(r)
            olist.append(r)

def graph(out_list,in_list,deps):
    for itm in out_list:
        print("resolved",itm,'->',','.join(deps[itm]))
    if in_list:
        for itm in out_list:
            print("unresolved",itm,'->',','.join(deps[itm]))

def check_dependencies(input_list,show_graph=False):
    deps = dependency_graph(input_list)
    temp_input_set = set(deps.keys())
    temp_output_list = []
    no_deps = get_no_dep_nodes(deps)
    transfer(temp_input_set,no_deps,temp_output_list)

    currently_resolved = set(temp_output_list)
    while temp_input_set:
        anything_resolved = False

        for node_name in temp_input_set:
            if deps[node_name] <= currently_resolved:
                temp_output_list.append(node_name)
                currently_resolved.add(node_name)
                anything_resolved = True

        temp_input_set -= currently_resolved
        if not anything_resolved:
            break

    res = None
    if show_graph:
        graph(temp_output_list,temp_input_set,deps)

    if temp_input_set:
        print("all deps not resolved ",node_name, temp_input_set)
        raise ValueError('Not all deps resolved')
    else:
        res =  temp_output_list

    return res