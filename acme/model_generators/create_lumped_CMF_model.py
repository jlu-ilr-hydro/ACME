# -*- coding: utf-8 -*-
"""
Created on Aug 15 13:28 2017
@author(s): Florian U. Jehn

This file is used to start the construction of a predefined CMF model. The
user only has to provide the forcing data and the kind of techniques (
Distribution, objective function, etc.).

The structure is created in such a way, that there is always at least one
connection to the outlet.
"""
import acme.model_generators._lumped_CMF_model_template as template
import acme.model_generators._lookup as lookup
import acme.genetics.genetic as genetic
import datetime
import random
import os


class LumpedCMFGenerator:
    # Define gen set
    # This is done so widespread to make it more readable and also allow
    #  it later to check for what is in what.
    # "first_layer" is excluded, as a model without any storage makes no sense.
    # The possible parameters are defined for the class as a whole as they
    # are equal for all instances and are easier to access this way.
    storages = ["snow", "canopy", "second_layer", "third_layer", "river"]
    connections = ["tr_first_out", "tr_first_river", "tr_first_third",
                   "tr_second_third", "tr_second_river_or_out",
                   "tr_third_river_or_out", "river_out"]
    snow_params = ["meltrate", "snow_melt_temp"]
    canopy_params = ["lai", "canopy_closure"]
    # ET params excluded as a ETact that is always ETpot makes no sense
    # et_params = ["etv0", "fetv0"]
    first_layer_params = ["beta_first_out", "beta_first_river",
                          "beta_first_second", "v0_first_out",
                          "v0_first_river", "v0_first_second"]
    second_layer_params = ["beta_second_river", "beta_second_third"]
    third_layer_params = ["beta_third_river"]
    river_params = ["beta_river_out"]
    params = (snow_params + canopy_params +
              # et_params +
              first_layer_params +
              second_layer_params + third_layer_params +
              river_params)
    gene_set = storages + connections + params

    # List to save all models that have been tested so far. The key is
    # the genes in the model and the value the best objective function
    models_so_far = {}

    def __init__(self, start_year,
                 end_year,
                 validation_time_span,

                 obj_func,
                 optimal_fitness,
                 Distribution,
                 algorithm,
                 et,

                 prec,
                 discharge,
                 t_mean,
                 t_min,
                 t_max,

                 max_age=50,
                 pool_size=10
                 ):
        """
        Sets everything up, ready to be solved.

        :param start_year: year for the start of the calibration period
        :param end_year: year for the end of the calibration period
        :param validation_time_span: time after end_year which should be
        used for calibration
        :param obj_func: the objective function that should be used (only
        the name is needed, all objective functions in spotpy are possible)
        :param Distribution: The way the parameters will be distributed (
        e.g. Weibull)
        :param et: Method for calculation of evapotranspiration
        """
        # Calibration/Validation stuff
        self.start_year = start_year
        self.end_year = end_year
        self.validation_time_span = validation_time_span
        # Get the functions and classes the match the user specified inputs.
        self.obj_func = lookup.get_obj_func(obj_func)
        self.optimal_fitness = optimal_fitness
        self.Distribution = lookup.get_distribution(Distribution)
        self.algorithm = lookup.get_algorithm(algorithm)
        self.et = lookup.get_evapotranspiration(et)
        # Forcing data
        self.data = {
            "prec": prec, 
            "discharge": discharge,
            "t_mean": t_mean,
            "t_min": t_min,
            "t_max": t_max
        }
        # Arguments for genetics behaviour
        self.max_age = max_age
        self.pool_size = pool_size


    def solve(self):
        """
        Starts the process of model selection.

        Calls the genetic file with all needed informations.
        :return: None, but writes the best found model to a file
        """
        # Make the needed variables available for the helper functions.
        data = self.data
        obj_func = self.obj_func
        algorithm = self.algorithm

        # Helper functions used as interface to genetic.

        def fn_create():
            return create()

        def fn_display(candidate):
            display(candidate, start_time)

        def fn_get_fitness(genes):
            return get_fitness(genes, data, obj_func, algorithm)

        def fn_mutate(genes):
            mutate(genes, fn_get_fitness)

        def fn_crossover(parent, donor):
            return crossover(parent, donor)

        start_time = datetime.datetime.now()

        # Give all definitions to the get_best function of genetic to start
        # the whole process of evolutionary selection
        best = genetic.get_best(fn_get_fitness, None, self.optimal_fitness,
                                None, fn_display, fn_mutate, fn_create,
                                max_age=self.max_age,
                                pool_size=self.pool_size,
                                crossover=fn_crossover)
        # Run the process until the desired fitness value is reached.
        while not self.optimal_fitness > best.fitness:
            pass

        # Write the best model to file.
        write_best_model(best)


def get_fitness(genes, data, obj_func, algorithm):
    """
    Calculates the fitness of a given genotype.

    :param genes: genotype that is to be tested for its fitness
    :param data: the weather data in the form of a dict of lists
    :param obj_func: the objective function that is to be used.
    :param algorithm: The sampling algorithm form Spotpy. For now the use of
                      dream is assumed.
    :return:
    """
    # Compare if the genes the function gets, have already been calculated
    #  as a model
    for old_model in LumpedCMFGenerator.models_so_far.keys():
        # Turn model in list version
        old_model_genes = old_model.split()
        # If so, simply return the fitness value of the old model
        if set(old_model_genes) == set(genes):
            return LumpedCMFGenerator.models_so_far[old_model]

    # If not call the template and run the model
    current_model = template.LumpedModelCMF(genes, data, obj_func)

    # Find out if the model should run parallel (for supercomputer)
    parallel = 'mpi' if 'OMPI_COMM_WORLD_SIZE' in os.environ else 'seq'

    sampler = algorithm(current_model, parallel=parallel, dbformat="noData")

    # The template runs until the predefined convergence value of dream is
    #  reached (or the maximal value for repetions is reached).
    sampler.sample(500, convergence_limit=1.6)

    # Extract the best value from the model
    best_like = sampler.bestlike

    # Save the current model in the all models list
    model_key = " ".join(genes)
    LumpedCMFGenerator.models_so_far[model_key] = best_like

    # Return best fitness value of all runs
    return best_like


def display(candidate, start_time):
    """
    Display the current candidate and his fitness
    :param candidate: Model/genotype that is to be displayed
    :param start_time: Time when the current program started
    :return: None
    """
    time_diff = datetime.datetime.now() - start_time
    print("Genes: {}\t\nFitness: {}\tStrategy: {}\tTime: {}".format(
        " ".join(map(str, candidate.genes)),
        candidate.fitness, candidate.Strategy.name, time_diff))


def mutate(genes, gene_set):
    """
    Mutates a genome
    :param genes: genes of a given individual
    :param gene_set: all possible genes.
    :param fn_get_fitness:
    :return: None (the list is directly manipulated)
    """
    mutation_type = random.choice(["add", "del", "swap"])
    max_changes = 3
    if mutation_type == "add":
        for _ in range(random.randint(1, max_changes)):
            # If the genes already contains all possible genes,
            # delete one gene and stop iteration
            if set(genes) == set(gene_set):
                random.shuffle(genes)
                genes.pop()
                break
            while True:
                new_gene = random.choice(gene_set)
                # Check if the random choice to avoid adding it again
                if new_gene not in genes:
                    genes.append(new_gene)
                    break

    elif mutation_type == "del":
        for _ in range(random.randint(1, max_changes)):
            # If the list is empty add an item and stop iteration
            if len(genes) == 0:
                new_gene = random.choice(gene_set)
                genes.append(new_gene)
                break
            # Pick a random genes
            random.shuffle(genes)
            genes.pop()

    elif mutation_type == "swap":
        for _ in range(random.randint(1, max_changes)):
            # Make a copy of the parent genes
            initial_genes = genes[:]
            # create a index for a random place in the parent genome
            index = random.randrange(0, len(genes))
            # take two random samples out of the gene set
            new_gene, alternate = random.sample(gene_set, 2)
            # replace the gene at index with another one, if it is randomly the
            # same, exchange it with the alternative.
            initial_genes[index] = (alternate if new_gene ==
                                    initial_genes[index]
                                    else
                                    new_gene)
    return


def crossover(first_parent, second_parent):
    """
    Performs a crossover between to genotypes. A single point crossover is
    used.
    :param first_parent: genotype of the first parent (list)
    :param second_parent: genotype of the second parent (list)
    :return: a new genotype (list)
    """
    # Select two random points in the length of the parent and donor genome
    index_first_parent = random.randint(0, len(first_parent))
    index_second_parent = random.randint(0, len(second_parent))
    # Take all the genes from before the point from parent and all the genes
    # from behind the point from behind the point
    part_first_parent = first_parent[:index_first_parent]
    part_second_parent = second_parent[index_second_parent:]
    # Combine the parts
    child_genes = part_first_parent + part_second_parent
    # Create a set out of it to avoid duplicates
    # then turn it back to a list and return it
    child_genes = list(set(child_genes))
    return child_genes


def create():
    """
    Creates a genotype after given rules.
    
    Allows creation in such a way, that a connection to the outlet is 
    guaranteed. 
    :param gene_set: all possible genes for a model
    :return: a genotype of a model
    """
    threshold = 1/3
    genes = []

    # Snow
    if random.random() < threshold:
        genes.append("snow")
        # Only add the snow parameter genes if there is a snow storage
        if random.random() < threshold:
            genes.append("meltrate")
        if random.random() < threshold:
            genes.append("snow_melt_temp")

    # Canopy
    if random.random() < threshold:
        genes.append("canopy")
        if random.random() < threshold:
            genes.append("canopy_closure")
        if random.random() < threshold:
            genes.append("lai")

    # Layers
    if random.random() < threshold:
        genes.append("second_layer")
        if random.random() < threshold:
            genes.append("third_layer")

    if random.random() < threshold:
        genes.append("river")

    # Connections first layer
    if random.random() < threshold:
        genes.append("tr_first_second")
        if random.random() < threshold:
            genes.append("beta_first_second")
        if random.random() < threshold:
            genes.append("v0_first_second")

    if random.random() < threshold:
        genes.append("tr_first_river")
        if random.random() < threshold:
            genes.append("beta_first_river")
        if random.random() < threshold:
            genes.append("v0_first_river")

    if random.random() < threshold:
        genes.append("tr_first_out")
        if random.random() < threshold:
            genes.append("beta_first_out")
        if random.random() < threshold:
            genes.append("v0_first_out")

    # Connections second layer
    if "second_layer" in genes:
        # loop through until second_layer has a connection so somewhere
        while "tr_second_third" not in genes or "tr_second_river" not in genes:
            if random.random() < threshold:
                genes.append("tr_second_third")
                if random.random() < threshold:
                    genes.append("beta_second_third")
            if random.random() < threshold:
                genes.append("tr_second_river")
                if random.random() < threshold:
                    genes.append("beta_second_river")

    # Connections third layer
    if "third_layer" in genes:
        # always add a connection, otherwise third_layer would be a dead end
        genes.append("tr_third_river")
        if random.random() < threshold:
            genes.append("beta_third_river")

    # River
    if "river" in genes:
        if random.random() < threshold:
            genes.append("beta_river_out")
    return genes


def write_all_model():
    """
    Writes all the models to a file.

    :return: None
    """
    pass


def check_for_connection(genes):
    """
    Determines if a there is a connection to the outlet and if not creates one.

    :param genes:
    :return:
    """
    to_outlet = False
    outgoing = []
    for connection in LumpedCMFGenerator.connections:
        if "out" in connection:
            outgoing.append(connection)
    for connection in outgoing:
        if connection in genes:
            to_outlet = True
            break
    if not to_outlet:
        genes.append("tr_first_out")
