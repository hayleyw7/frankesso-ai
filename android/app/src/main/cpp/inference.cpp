#include <jni.h>
#include "llama.h"

#include <atomic>
#include <chrono>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr int context_tokens = 1536;
constexpr int response_tokens = 192;
using Clock = std::chrono::steady_clock;
constexpr auto progress_interval = std::chrono::milliseconds(100);
struct Session {
    std::unique_ptr<llama_model, decltype(&llama_model_free)> model{nullptr, llama_model_free};
    std::unique_ptr<llama_context, decltype(&llama_free)> context{nullptr, llama_free};
    std::atomic_bool canceled{false};
};

struct ReplyControl {
    const std::atomic_bool &canceled;
    const Clock::time_point deadline;

    bool expired() const { return Clock::now() >= deadline; }
    bool stopped() const { return canceled.load(std::memory_order_relaxed) || expired(); }

    static bool abort_callback(void *data) {
        return static_cast<const ReplyControl *>(data)->stopped();
    }
};

class ScopedAbort {
public:
    ScopedAbort(llama_context *ctx, ReplyControl &control) : ctx_(ctx) {
        llama_set_abort_callback(ctx_, ReplyControl::abort_callback, &control);
    }
    ~ScopedAbort() {
        // Workers must not retain a pointer to the reply's stack state.
        llama_synchronize(ctx_);
        llama_set_abort_callback(ctx_, nullptr, nullptr);
    }
    ScopedAbort(const ScopedAbort &) = delete;
    ScopedAbort &operator=(const ScopedAbort &) = delete;
private:
    llama_context *ctx_;
};

void fail(JNIEnv *env, const char *message, const char *type = "java/lang/IllegalStateException") {
    if (!env->ExceptionCheck()) env->ThrowNew(env->FindClass(type), message);
}

jbyteArray as_bytes(JNIEnv *env, const std::string &value) {
    jbyteArray buffer = env->NewByteArray(static_cast<jsize>(value.size()));
    if (buffer && !value.empty()) {
        env->SetByteArrayRegion(buffer, 0, static_cast<jsize>(value.size()),
                                reinterpret_cast<const jbyte *>(value.data()));
    }
    return buffer;
}
}

extern "C" JNIEXPORT jlong JNICALL
Java_app_frankesso_android_NativeModel_nativeOpen(JNIEnv *env, jclass, jstring path) {
    const char *chars = env->GetStringUTFChars(path, nullptr);
    if (!chars) return 0;
    try {
        static std::once_flag once;
        std::call_once(once, [] { llama_backend_init(); });
        auto session = std::make_unique<Session>();
        auto model_params = llama_model_default_params();
        model_params.n_gpu_layers = 0;
        session->model.reset(llama_model_load_from_file(chars, model_params));
        if (!session->model) throw std::runtime_error("The local model could not be opened.");
        auto params = llama_context_default_params();
        params.n_ctx = context_tokens;
        params.n_batch = context_tokens;
        params.n_ubatch = 128;
        params.n_threads = 3;
        params.n_threads_batch = 3;
        session->context.reset(llama_init_from_model(session->model.get(), params));
        if (!session->context) throw std::runtime_error("The phone could not allocate a chat session.");
        env->ReleaseStringUTFChars(path, chars);
        return reinterpret_cast<jlong>(session.release());
    } catch (const std::exception &e) {
        env->ReleaseStringUTFChars(path, chars);
        fail(env, e.what());
        return 0;
    }
}

extern "C" JNIEXPORT jbyteArray JNICALL
Java_app_frankesso_android_NativeModel_nativeReply(JNIEnv *env, jclass, jlong handle,
                                                   jbyteArray prompt, jobject sink, jint timeout_ms) {
    try {
        auto *session = reinterpret_cast<Session *>(handle);
        const auto *vocab = llama_model_get_vocab(session->model.get());
        auto *ctx = session->context.get();
        ReplyControl control{session->canceled, Clock::now() + std::chrono::milliseconds(timeout_ms)};
        ScopedAbort abort(ctx, control);
        const jclass sink_class = env->GetObjectClass(sink);
        if (!sink_class) return nullptr;
        const jmethodID report = env->GetMethodID(sink_class, "onBytes", "([B)V");
        env->DeleteLocalRef(sink_class);
        if (!report) return nullptr;
        std::string text(env->GetArrayLength(prompt), '\0');
        env->GetByteArrayRegion(prompt, 0, static_cast<jsize>(text.size()), reinterpret_cast<jbyte *>(text.data()));
        if (env->ExceptionCheck()) return nullptr;
        std::vector<llama_token> tokens(context_tokens);
        const int count = llama_tokenize(vocab, text.data(), static_cast<int32_t>(text.size()),
                                         tokens.data(), context_tokens, false, true);
        if (count <= 0 || count > context_tokens - response_tokens) {
            throw std::runtime_error("That message is too long for the local model.");
        }
        const auto timed_out = [&] {
            if (control.expired() && !session->canceled.load(std::memory_order_relaxed)) {
                fail(env, "The local reply exceeded its time limit.", "java/util/concurrent/TimeoutException");
                return true;
            }
            return false;
        };
        if (timed_out()) return nullptr;
        if (control.stopped()) return as_bytes(env, "");
        llama_memory_clear(llama_get_memory(ctx), true);
        const auto prompt_status = llama_decode(ctx, llama_batch_get_one(tokens.data(), count));
        if (timed_out()) return nullptr;
        if (session->canceled.load(std::memory_order_relaxed)) return as_bytes(env, "");
        if (prompt_status != 0) throw std::runtime_error("The local model could not read the message.");
        std::unique_ptr<llama_sampler, decltype(&llama_sampler_free)> sampler(
            llama_sampler_chain_init(llama_sampler_chain_default_params()), llama_sampler_free);
        if (!sampler) throw std::runtime_error("The local sampler could not start.");
        llama_sampler_chain_add(sampler.get(), llama_sampler_init_top_k(40));
        llama_sampler_chain_add(sampler.get(), llama_sampler_init_top_p(0.9f, 1));
        llama_sampler_chain_add(sampler.get(), llama_sampler_init_temp(0.7f));
        llama_sampler_chain_add(sampler.get(), llama_sampler_init_dist(LLAMA_DEFAULT_SEED));
        std::string output;
        std::vector<char> piece(128);
        auto last_progress = Clock::time_point::min();
        bool sent_progress = false;
        for (int i = 0; i < response_tokens && !control.stopped(); ++i) {
            auto token = llama_sampler_sample(sampler.get(), ctx, -1);
            if (llama_vocab_is_eog(vocab, token)) break;
            auto n = llama_token_to_piece(vocab, token, piece.data(), piece.size(), 0, false);
            if (n < 0) {
                piece.resize(static_cast<size_t>(-n));
                n = llama_token_to_piece(vocab, token, piece.data(), piece.size(), 0, false);
            }
            if (n < 0) throw std::runtime_error("The local model returned unreadable text.");
            output.append(piece.data(), static_cast<size_t>(n));
            const auto now = Clock::now();
            if (!output.empty() && (!sent_progress || now - last_progress >= progress_interval)) {
                jbyteArray partial = as_bytes(env, output);
                if (!partial || env->ExceptionCheck()) return nullptr;
                env->CallVoidMethod(sink, report, partial);
                env->DeleteLocalRef(partial);
                if (env->ExceptionCheck()) return nullptr;
                last_progress = now;
                sent_progress = true;
            }
            if (i + 1 < response_tokens && !control.stopped()) {
                const auto status = llama_decode(ctx, llama_batch_get_one(&token, 1));
                if (status != 0 && !control.stopped()) {
                    throw std::runtime_error("The local model stopped responding.");
                }
            }
        }
        if (timed_out()) return nullptr;
        return as_bytes(env, output);
    } catch (const std::exception &e) {
        fail(env, e.what());
        return nullptr;
    }
}

extern "C" JNIEXPORT void JNICALL
Java_app_frankesso_android_NativeModel_nativeClose(JNIEnv *, jclass, jlong handle) {
    delete reinterpret_cast<Session *>(handle);
}

extern "C" JNIEXPORT void JNICALL
Java_app_frankesso_android_NativeModel_nativeSetCanceled(JNIEnv *, jclass, jlong handle, jboolean canceled) {
    auto *session = reinterpret_cast<Session *>(handle);
    session->canceled.store(canceled == JNI_TRUE, std::memory_order_relaxed);
}
