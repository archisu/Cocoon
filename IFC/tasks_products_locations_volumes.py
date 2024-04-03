# Import necessary libraries and functions. 

import os
import ifcopenshell
import ifcopenshell.api
from ifcopenshell.api import run
import ifcopenshell.util.sequence
import ifcopenshell.util.placement
from collections import Counter
import ifcopenshell.geom
import ifcopenshell.util.shape

### DEFINITIONS ###

# Retrieve all IFC Tasks and their hierarchical information. 

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

# Find the highest level in hirearchy, since the tasks on this level will be the first tasks to be completed in the schedule. 

def print_task_levels(leaf_tasks):
    for task in leaf_tasks[max_level]:
        print(f"Task ID: {task.id()}, Task Name: {task.Name if hasattr(task, 'Name') else 'N/A'}, Level: {max_level}")

# Find all relevant tasks for the desired IFC product, using keywords such as "wall, slab, beam" etc.

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

# Get tasks predecessor information. 

def get_predecessor(task):
    # Use the BlenderBIM API utility functions
    predec = ifcopenshell.util.sequence.get_sequence_assignment(task, sequence='predecessor')
    return predec
    
# Find tasks without predecessors, since these tasks have to be carried out first. This definition helps avoid scheduling problems, such as scheduling a wall finishing job before the wall assembly job.

# def find_initial_tasks(tasks):
#     tasks_wo_predecs = []
#     for task in tasks:
#         predecs = get_predecessor(task)
#         if not predecs:
#             tasks_wo_predecs.append(task)
#     return tasks_wo_predecs

def find_initial_tasks(tasks):
    min_predecs_count = float('inf') # Initialize with positive infinity to find minimum
    tasks_with_min_predecs = []

    for task in tasks:
        predecs = get_predecessor(task)
        predecs_count = len(predecs)

        if predecs_count < min_predecs_count:
            min_predecs_count = predecs_count
            tasks_with_min_predecs = [task]
        elif predecs_count == min_predecs_count:
            tasks_with_min_predecs.append(task)

    return tasks_with_min_predecs

# Find tasks' products.

def find_task_products(task):

    products = ifcopenshell.util.sequence.get_direct_task_outputs(task)

    return products

# Create a new IFC model containing only the relevant IFC products and their 3D geometric representation, based on given tasks.

def create_task_product_model(tasks):

    # Create a new IFC model.
    
    walls_model = ifcopenshell.file(schema=model.schema)
    walls_project = run("root.create_entity", walls_model, ifc_class="IfcProject", name="Walls")
    
    # TIP: 3D geometries will not be represented in the file if you don't assign units.

    length_unit = "MILLIMETER"
    run("unit.assign_unit", walls_model, length_unit)
    
    context = run("context.add_context", walls_model, context_type="Model")
    body = run("context.add_context", walls_model, context_type="Model",
        context_identifier="Body", target_view="MODEL_VIEW", parent=context)

    # Add relevant products into the model using find_task_products definition.. 

    for task in tasks: 
        products = find_task_products(task)
        for product in products:
            walls_model.add(product)

    # Write the new IFC model.
    
    walls_model.write('walls_model2.ifc')
    return walls_model

# Find coordinates of a product.

def find_coordinates(products):
    matrices = []
    for product in products:
        matrix = ifcopenshell.util.placement.get_local_placement(product.ObjectPlacement)
        matrices.append(matrix)
    return matrices

# Find center points of products. This location will be assumed execution point for each robot for their respective tasks. 

def find_center_point(product):
    matrix = ifcopenshell.util.placement.get_local_placement(product.ObjectPlacement)
    # get location
    location = matrix[:3, 3]
    # Calculate center point
    center_point = tuple(location)
    return center_point

# Create a dictionary with tasks and center points of their respective products. 

def match_tasks_w_cpts(tasks):
    center_points = {}

    for task in tasks:
        all_cpt = []
        products = find_task_products(task)
        for product in products:
            center_point = find_center_point(product)
            all_cpt.append(center_point)
        center_points[task] = all_cpt
    print(center_points)
    return center_points

# Create a dictionary with tasks and their boundary points for obstacle generation. 

def match_tasks_w_bndpts(tasks):
    bnd_points = {}

    for task in tasks: 
        all_bndpts = []
        products = find_task_products(task)

        for product in products:
            bnd_pt = get_bottom_vertices(product)
            all_bndpts.append(bnd_pt)
        bnd_points[task] = all_bndpts

    print(bnd_points)
    return bnd_points

def find_task_volumes(tasks):
    task_vol = {}

    for task in tasks:
        all_vol = []
        products = find_task_products(task)
        for product in products:
            vol = get_volume(product)
            all_vol.append(vol)
        task_vol[task] = all_vol
    print(task_vol)
    return task_vol

### vertices and volume experiments

def get_bottom_vertices(product):

    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings,product)
    verts = ifcopenshell.util.shape.get_vertices(shape.geometry)

    min_y = min(verts, key = lambda vertex: vertex[1])[1]
    bottom_verts = [v.tolist() for v in verts if v[1] == min_y]

    return bottom_verts

def get_volume(product):
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings,product)
    volume = ifcopenshell.util.shape.get_volume(shape.geometry)
    converted_vol = volume / 1_000_000_000 # conversion from cubic millimeters to cubic meters
    return converted_vol


# IFC file size checker. Use this to check if the new IFC file is properly written. 

def get_ifc_file_size(file_path):
    try:
        size_bytes = os.path.getsize(file_path)
        size_kb = size_bytes / 1024.0
        size_mb = size_kb / 1024.0
        return size_bytes, size_kb, size_mb
    except FileNotFoundError:
        return None

### MAIN FUNCTION ###

# Define a main function to create the robot world and a dictionary which stores the locations of tasks. 

if __name__=="__main__":
    
    # Open the IFC model, and retrieve necessary information using respective definitions. 

    directory = "D:\Academic\WS2023-24\PrototypingProject\Prototype\src\Cocoon_Prototype_2024\IFC"
    ifc_file_path = os.path.join(directory, "basemodel.ifc")

    model = ifcopenshell.open(ifc_file_path)
    tasks = model.by_type("IfcTask")
    leaf_tasks = print_all_tasks(model)
    max_level = max(leaf_tasks.keys())
    wall_tasks = filter_tasks_by_keyword(leaf_tasks, "wall")
    initial_wall_tasks = find_initial_tasks(wall_tasks)
    # fix this part. since evry task has a predecessor now, it returns an empty list. FIXED
    # but now not getting all the initial wall tasks 
    print(initial_wall_tasks)
    walls_model = create_task_product_model(initial_wall_tasks)

    # Check new IFC model

    new_file_size = get_ifc_file_size("walls_model2.ifc")
    print(new_file_size)

    # Create task-location dictionary with center points of products#
    
    match_tasks_w_cpts(initial_wall_tasks)

    # Get obstacle information

    # new_wall = walls_model.by_type('IfcWall')[0]
    # get_volume(new_wall)

    # Outputs task products and boundary points (4 vertices that define the boundary in plan view)
    match_tasks_w_bndpts(initial_wall_tasks)

    # Outputs a dictionary of tasks and sum volume of all its products
    find_task_volumes(initial_wall_tasks)


 