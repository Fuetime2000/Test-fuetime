def avg(sequence):
    """Calculate the average of a sequence of numbers."""
    if not sequence:
        return 0
    return sum(sequence) / len(sequence)
