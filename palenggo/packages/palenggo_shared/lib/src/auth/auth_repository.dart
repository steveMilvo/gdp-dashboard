import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart';

/// Phone-OTP auth using Firebase Auth (spec §12 Phase 1, step 2).
class AuthRepository {
  AuthRepository(this._auth);

  final FirebaseAuth _auth;

  Stream<User?> authStateChanges() => _auth.authStateChanges();

  User? get currentUser => _auth.currentUser;

  /// Sends an OTP to [phoneE164] (must include `+` and country code).
  ///
  /// Returns a verification id that must be passed back to [verifyOtp]
  /// alongside the SMS code the user typed in.
  Future<String> sendOtp(String phoneE164) async {
    final completer = Completer<String>();
    await _auth.verifyPhoneNumber(
      phoneNumber: phoneE164,
      timeout: const Duration(seconds: 60),
      verificationCompleted: (PhoneAuthCredential credential) async {
        // Android-only auto-retrieval. Sign in directly when it fires.
        try {
          await _auth.signInWithCredential(credential);
        } catch (_) {
          // If auto sign-in fails we still want the manual flow to proceed.
        }
      },
      verificationFailed: (FirebaseAuthException e) {
        if (!completer.isCompleted) completer.completeError(e);
      },
      codeSent: (String verificationId, int? _) {
        if (!completer.isCompleted) completer.complete(verificationId);
      },
      codeAutoRetrievalTimeout: (String _) {},
    );
    return completer.future;
  }

  Future<UserCredential> verifyOtp({
    required String verificationId,
    required String smsCode,
  }) {
    final credential = PhoneAuthProvider.credential(
      verificationId: verificationId,
      smsCode: smsCode,
    );
    return _auth.signInWithCredential(credential);
  }

  Future<void> signOut() => _auth.signOut();
}
