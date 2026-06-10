#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "math_core.hpp"

namespace py = pybind11;

PYBIND11_MODULE(math_core, m) {
    m.doc() = "C++ Core Math functions for the 5D Manifold Memory Engine";

    py::class_<llm_kosh::MemoryTensor>(m, "MemoryTensor")
        .def(py::init<>())
        .def_readwrite("id", &llm_kosh::MemoryTensor::id)
        .def_readwrite("embedding", &llm_kosh::MemoryTensor::embedding)
        .def_readwrite("t", &llm_kosh::MemoryTensor::t)
        .def_readwrite("M_sal", &llm_kosh::MemoryTensor::M_sal);

    m.def("project_subspace", &llm_kosh::project_subspace,
          "Applies a diagonal lens projection matrix to a vector",
          py::arg("vec"), py::arg("lens"));

    m.def("weighted_cosine_similarity", &llm_kosh::weighted_cosine_similarity,
          "Computes weighted cosine similarity between two projected vectors",
          py::arg("a"), py::arg("b"), py::arg("w"));

    m.def("temporal_euclidean_decay", &llm_kosh::temporal_euclidean_decay,
          "Computes exponential distance decay",
          py::arg("q_t"), py::arg("m_t"), py::arg("alpha"));

    m.def("temporal_vector_decay", &llm_kosh::temporal_vector_decay,
          "Computes exponential temporal vector distance decay",
          py::arg("q"), py::arg("m"), py::arg("w"), py::arg("alpha"));

    m.def("mahalanobis_distance", &llm_kosh::mahalanobis_distance,
          "Computes Mahalanobis distance between two vectors using weights",
          py::arg("a"), py::arg("b"), py::arg("w"));
}
