#pragma once
#include <string>
#include <vector>
#include <cmath>
#include <stdexcept>

namespace llm_kosh {

struct MemoryTensor {
    std::string id;
    std::vector<float> embedding; // dimension 1536
    float t;                      // timestamp
    float M_sal;                  // salience weight
};

// Applies a diagonal lens projection matrix (represented as a sparse diagonal vector of 1s and 0s)
inline std::vector<float> project_subspace(const std::vector<float>& vec, const std::vector<float>& lens) {
    if (vec.size() != lens.size()) {
        throw std::invalid_argument("Vector and lens sizes must match");
    }
    std::vector<float> result(vec.size(), 0.0f);
    const size_t n = vec.size();
    const float* v_ptr = vec.data();
    const float* l_ptr = lens.data();
    float* r_ptr = result.data();

    #pragma omp simd
    for (size_t i = 0; i < n; ++i) {
        r_ptr[i] = v_ptr[i] * l_ptr[i];
    }
    return result;
}

// Computes the weighted cosine similarity
inline float weighted_cosine_similarity(const std::vector<float>& a, const std::vector<float>& b, const std::vector<float>& w) {
    if (a.size() != b.size() || a.size() != w.size()) {
        throw std::invalid_argument("Vector and weight sizes must match");
    }
    double dot = 0.0;
    double norm_a = 0.0;
    double norm_b = 0.0;
    const size_t n = a.size();
    const float* a_ptr = a.data();
    const float* b_ptr = b.data();
    const float* w_ptr = w.data();

    #pragma omp simd reduction(+:dot,norm_a,norm_b)
    for (size_t i = 0; i < n; ++i) {
        float wa = w_ptr[i] * a_ptr[i];
        float wb = w_ptr[i] * b_ptr[i];
        dot += wa * b_ptr[i];
        norm_a += wa * a_ptr[i];
        norm_b += wb * b_ptr[i];
    }

    if (norm_a <= 0.0 || norm_b <= 0.0) {
        return 0.0f;
    }
    return static_cast<float>(dot / (std::sqrt(norm_a) * std::sqrt(norm_b)));
}

// Computes the exponential distance decay exp(-alpha * |q_t - m_t|)
inline float temporal_euclidean_decay(float q_t, float m_t, float alpha) {
    float diff = std::abs(q_t - m_t);
    return std::exp(-alpha * diff);
}

// Vector version of temporal/salience distance decay
inline float temporal_vector_decay(const std::vector<float>& q, const std::vector<float>& m, const std::vector<float>& w, float alpha) {
    if (q.size() != m.size() || q.size() != w.size()) {
        throw std::invalid_argument("Vector and weight sizes must match");
    }
    double sum_sq = 0.0;
    const size_t n = q.size();
    const float* q_ptr = q.data();
    const float* m_ptr = m.data();
    const float* w_ptr = w.data();

    #pragma omp simd reduction(+:sum_sq)
    for (size_t i = 0; i < n; ++i) {
        float diff = q_ptr[i] - m_ptr[i];
        sum_sq += w_ptr[i] * diff * diff;
    }
    return static_cast<float>(std::exp(-alpha * std::sqrt(sum_sq)));
}

} // namespace llm_kosh
