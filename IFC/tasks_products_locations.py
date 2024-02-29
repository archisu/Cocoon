import ifcopenshell
import ifcopenshell.api
from ifcopenshell.api import run
import ifcopenshell.util.sequence
import ifcopenshell.util.placement
from collections import Counter

print(ifcopenshell.version)

model = ifcopenshell.open("basemodel.ifc")

tasks = model.by_type("IfcTask")

def print_all_tasks(ifc_model):
    printed_tasks = set()
    leaf_tasks = {}

    def print_task_with_gap(task, level):
        print("   " * level + "Task ID:", task.id())
        print("   " * level + "Task Name:", task.Name if hasattr(task, "Name") else "N/A")
        print("   " * level + "-" * 40)
        printed_tasks.add(task.id())

        if level in leaf_tasks:
            leaf_tasks[level].append(task)
        else: 
            leaf_tasks[level] = [task]


    def print_nested_tasks(tasks, current_level=0):
        for task in tasks:
            if task.id() not in printed_tasks:
                print_task_with_gap(task, current_level)
                nested_tasks = ifcopenshell.util.sequence.get_nested_tasks(task)
                if nested_tasks:
                    print_nested_tasks(nested_tasks, current_level + 1)

    print_nested_tasks(tasks)
    return leaf_tasks

leaf_tasks = print_all_tasks(model)
max_level = max(leaf_tasks.keys())

def print_task_levels(leaf_tasks):
    for task in leaf_tasks[max_level]:
        print(f"Task ID: {task.id()}, Task Name: {task.Name if hasattr(task, 'Name') else 'N/A'}, Level: {max_level}")

def filter_tasks_by_keyword(tasks, keyword):
    filtered_tasks = []
    for task_list in tasks.values():
        for task in task_list:
            if keyword.lower() in task.Name.lower():
                filtered_tasks.append(task)
    print('    ' f'{keyword} tasks') 
    for task in filtered_tasks:
        print(f"Task ID: {task.id()}, Task Name: {task.Name if hasattr(task, 'Name') else 'N/A'}, Level: {max_level}")
    return filtered_tasks

def get_predecessor(task):
    # Use the BlenderBIM API utility functions
    predec = ifcopenshell.util.sequence.get_sequence_assignment(task, sequence='predecessor')
    return predec

def find_initial_tasks(tasks):
    tasks_wo_predecs = []
    for task in tasks:
        predecs = get_predecessor(task)
        if not predecs:
            tasks_wo_predecs.append(task)
    return tasks_wo_predecs


print_all_tasks(model)
print_task_levels(leaf_tasks)

wall_tasks = filter_tasks_by_keyword(leaf_tasks, "wall")
initial_wall_tasks = find_initial_tasks(wall_tasks)


# the new model to write the walls
walls_model = ifcopenshell.file(schema=model.schema)

walls_project = run("root.create_entity", walls_model, ifc_class="IfcProject", name="Walls")

### TIP: 3D geometries will not be represented in the file if you don't assign units.

# Specify custom units
length_unit = "MILLIMETER"

# Assign custom units using unit.assign_unit
run("unit.assign_unit", walls_model, length_unit)

context = run("context.add_context", walls_model, context_type="Model")
body = run("context.add_context", walls_model, context_type="Model",
    context_identifier="Body", target_view="MODEL_VIEW", parent=context)


def find_task_products(tasks):
    outputs = []
    for task in tasks: 
        products = ifcopenshell.util.sequence.get_direct_task_outputs(task)
        for product in products:
            # ifcopenshell.api.run("project.append_asset", model, element=output)
            walls_model.add(product)
            outputs.append(product)
    return outputs



walls = find_task_products(initial_wall_tasks)
walls_model.write('walls_model.ifc')
print(walls)


### location ###


leaf_tasks = print_all_tasks(model)
max_level = max(leaf_tasks.keys())
wall_tasks = filter_tasks_by_keyword(leaf_tasks, "wall")
initial_wall_tasks = find_initial_tasks(wall_tasks)
walls = find_task_products(initial_wall_tasks)

def find_coordinates(products):
    matrices = []
    for product in products:
        matrix = ifcopenshell.util.placement.get_local_placement(product.ObjectPlacement)
        matrices.append(matrix)
    return matrices

find_coordinates(walls)

def find_center_point(product):
    matrix = ifcopenshell.util.placement.get_local_placement(product.ObjectPlacement)
    # get location
    location = matrix[:3, 3]
    # Calculate center point
    center_point = tuple(location)
    return center_point

def match_tasks_w_points(tasks):
    center_points = {}
    products = find_task_products(tasks)
    for product in products:
        center_point = find_center_point(product)
        center_points[product] = center_point
    return center_points

# OUTPUTS A DICTIONARY OF A TASKS PRODUCTS AND LOCATION
match_tasks_w_points(initial_wall_tasks)