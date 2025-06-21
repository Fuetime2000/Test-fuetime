// Initialize DataTable with search functionality
function initializeDataTable(tableId, translations) {
    return $(tableId).DataTable({
        order: [[0, "desc"]],
        language: translations
    });
}

// Handle admin panel search
$(document).ready(function() {
    // Get the search input and search button
    const searchInput = $('.navbar-search input[aria-label="Search"]');
    const searchButton = $('.navbar-search button');

    // Find all DataTables on the page
    const tables = $('table.table').map(function() {
        return $(this).DataTable();
    }).get();

    // Handle search input
    searchInput.on('keyup', function() {
        const searchTerm = $(this).val();
        tables.forEach(table => {
            table.search(searchTerm).draw();
        });
    });

    // Handle search button click
    searchButton.on('click', function() {
        const searchTerm = searchInput.val();
        tables.forEach(table => {
            table.search(searchTerm).draw();
        });
    });

    // Handle form submission (prevent default and trigger search)
    $('.navbar-search').on('submit', function(e) {
        e.preventDefault();
        searchButton.click();
    });
});

