const API_URL = "https://sadu-pavan.onrender.com";
fetch(`${API_URL}/names`)
    .then(response => response.json())
    .then(people => {

        const namesList = document.getElementById("names-list");

        people.forEach(person => {

            const button = document.createElement("button");

            button.textContent = person.name;

            button.onclick = () => {
                showDetails(person.id);
            };

            namesList.appendChild(button);
            namesList.appendChild(document.createElement("br"));
        });
    })
    .catch(error => {
        console.error("Error:", error);
    });


function showDetails(id) {

    fetch(`${API_URL}/names/${id}`)
        .then(response => response.json())
        .then(person => {

            const details = document.getElementById("details");

            details.innerHTML = `
                <p><strong>Name:</strong> ${person.name}</p>
                <p><strong>Age:</strong> ${person.details.age}</p>
                <p><strong>City:</strong> ${person.details.city}</p>
                <p><strong>Email:</strong> ${person.details.email}</p>
            `;
        })
        .catch(error => {
            console.error("Details Error:", error);
        });
}