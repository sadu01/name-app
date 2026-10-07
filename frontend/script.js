const API_URL = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000"
    : "https://sadu-pavan.onrender.com";

const details = document.getElementById("details");

function showDetails(person) {
    details.innerHTML = `
        <p><strong>ID:</strong> ${person.id}</p>
        <p><strong>Name:</strong> ${person.name}</p>
        <p><strong>Age:</strong> ${person.details.age}</p>
        <p><strong>City:</strong> ${person.details.city}</p>
        <p><strong>Email:</strong> ${person.details.email}</p>
    `;
}

function showError(message) {
    details.textContent = message;
}

function validateName(name) {
    if (!/^[\p{L}]+(?: +[\p{L}]+)*$/u.test(name)) {
        throw new Error("Name must contain letters and spaces only");
    }
}

function validateAge(ageInput) {
    if (!/^\d+$/.test(ageInput)) {
        throw new Error("Age must contain numbers only");
    }
    const age = Number(ageInput);
    if (!Number.isInteger(age) || age < 1 || age > 110) {
        throw new Error("Age must be a whole number from 1 to 110");
    }
    return age;
}

function validateEmail(email) {
    if (!email.includes("@")) {
        throw new Error("Email must contain @");
    }
}

function renderPeople(people) {
    const namesList = document.getElementById("names-list");
    namesList.innerHTML = "";

    people.forEach(person => {
        const row = document.createElement("div");

        const getButton = document.createElement("button");
        getButton.textContent = person.name;
        getButton.onclick = () => getPerson(person.id);

        const deleteButton = document.createElement("button");
        deleteButton.textContent = "Delete";
        deleteButton.onclick = () => deletePerson(person.id);

        row.append(getButton, deleteButton);
        namesList.appendChild(row);
    });
}

function getNames() {
    fetch(`${API_URL}/names`)
        .then(response => {
            if (!response.ok) {
                throw new Error("Unable to load people");
            }
            return response.json();
        })
        .then(people => {
            renderPeople(people);
        })
        .catch(error => {
            showError(error.message);
        });
}

function getPerson(id) {
    fetch(`${API_URL}/names/${id}`)
        .then(response => {
            if (!response.ok) {
                throw new Error("Person not found");
            }
            return response.json();
        })
        .then(showDetails)
        .catch(error => showError(error.message));
}

const modal = document.getElementById("field-modal");
const modalTitle = document.getElementById("modal-title");
const modalInstruction = document.getElementById("modal-instruction");
const modalInput = document.getElementById("modal-input");
const modalNext = document.getElementById("modal-next");
const modalCancel = document.getElementById("modal-cancel");

let modalCallback = null;
let modalValues = null;

function openModal({ title, instruction, inputType = "text", value = "" }) {
    modalTitle.textContent = title;
    modalInstruction.textContent = instruction;
    modalInput.type = inputType;
    modalInput.value = value;
    modalInput.focus();
    modalInput.select();
    modal.classList.add("visible");
    modal.setAttribute("aria-hidden", "false");
}

function closeModal() {
    modal.classList.remove("visible");
    modal.setAttribute("aria-hidden", "true");
    modalInput.value = "";
}

function collectField(fieldName, label, type = "text", defaultValue = "") {
    return new Promise((resolve, reject) => {
        modalCallback = value => {
            const currentValue = String(value ?? "").trim();
            if (currentValue === "") {
                reject(new Error(`${fieldName} is required`));
                return;
            }
            resolve(currentValue);
        };

        openModal({
            title: label,
            instruction: `Enter ${fieldName.toLowerCase()}:`,
            inputType: type,
            value: defaultValue,
        });
    });
}

async function addPerson() {
    try {
        closeModal();
        const name = await collectField("Name", "Add person name");
        validateName(name);
        const ageInput = await collectField("Age", "Add person age", "number");
        const age = validateAge(ageInput);
        const city = await collectField("City", "Add person city");
        const email = await collectField("Email", "Add person email", "email");
        validateEmail(email);

        const person = { name, details: { age, city, email } };
        const response = await fetch(`${API_URL}/names`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(person),
        });

        if (!response.ok) {
            throw new Error("Unable to add person");
        }

        const createdPerson = await response.json();
        showDetails(createdPerson);
        getNames();
    } catch (error) {
        showError(error.message);
    }
}

async function updatePerson() {
    try {
        closeModal();
        const idInput = await collectField("Person ID", "Update person ID", "number");
        const id = Number(idInput);
        if (!Number.isInteger(id) || id < 1) {
            throw new Error("Enter a valid person ID");
        }

        const name = await collectField("Name", "Enter new name");
        validateName(name);
        const ageInput = await collectField("Age", "Enter new age", "number");
        const age = validateAge(ageInput);
        const city = await collectField("City", "Enter new city");
        const email = await collectField("Email", "Enter new email", "email");
        validateEmail(email);

        const updates = { name, details: { age, city, email } };
        const response = await fetch(`${API_URL}/names/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(updates),
        });

        if (!response.ok) {
            throw new Error("Unable to update person");
        }

        const updatedPerson = await response.json();
        showDetails(updatedPerson);
        getNames();
    } catch (error) {
        showError(error.message);
    }
}

function deletePerson(id) {
    fetch(`${API_URL}/names/${id}`, { method: "DELETE" })
        .then(response => {
            if (!response.ok) {
                throw new Error("Unable to delete person");
            }
            return response.json();
        })
        .then(() => {
            showError(`Person ${id} deleted.`);
            getNames();
        })
        .catch(error => showError(error.message));
}

modalNext.addEventListener("click", () => {
    if (modalCallback) {
        modalCallback(modalInput.value);
        closeModal();
        modalCallback = null;
    }
});

modalCancel.addEventListener("click", () => {
    closeModal();
    modalCallback = null;
});

modalInput.addEventListener("keydown", event => {
    if (event.key === "Enter") {
        event.preventDefault();
        modalNext.click();
    }
    if (event.key === "Escape") {
        modalCancel.click();
    }
});

document.getElementById("add-name-button").addEventListener("click", addPerson);
document.getElementById("get-form").addEventListener("submit", event => {
    event.preventDefault();
    getPerson(event.currentTarget.id.value);
});
document.getElementById("update-person-button").addEventListener("click", updatePerson);
document.getElementById("delete-form").addEventListener("submit", event => {
    event.preventDefault();
    deletePerson(event.currentTarget.id.value);
});

getNames();