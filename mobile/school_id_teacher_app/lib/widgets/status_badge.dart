import 'package:flutter/material.dart';
import '../constants/app_colors.dart';

class StatusBadge extends StatelessWidget {
  final String status;
  final bool isVerification;

  const StatusBadge({
    super.key,
    required this.status,
    this.isVerification = true,
  });

  @override
  Widget build(BuildContext context) {
    Color bg;
    Color text;
    IconData icon;
    String label = status;

    final upper = status.toUpperCase();

    if (isVerification) {
      switch (upper) {
        case 'VERIFIED':
          bg = AppColors.verifiedBg;
          text = AppColors.verifiedText;
          icon = Icons.check_circle;
          label = "Verified";
          break;
        case 'SUBMITTED':
          bg = AppColors.submittedBg;
          text = AppColors.submittedText;
          icon = Icons.hourglass_top;
          label = "Submitted";
          break;
        case 'REJECTED':
          bg = AppColors.rejectedBg;
          text = AppColors.rejectedText;
          icon = Icons.cancel;
          label = "Rejected";
          break;
        default:
          bg = AppColors.pendingBg;
          text = AppColors.pendingText;
          icon = Icons.schedule;
          label = "Pending";
      }
    } else {
      switch (upper) {
        case 'ACTIVE':
          bg = AppColors.activeBg;
          text = AppColors.activeText;
          icon = Icons.shield_outlined;
          label = "Active";
          break;
        case 'REVOKED':
          bg = AppColors.rejectedBg;
          text = AppColors.rejectedText;
          icon = Icons.block;
          label = "Revoked";
          break;
        default:
          bg = AppColors.pendingBg;
          text = AppColors.pendingText;
          icon = Icons.history;
          label = status;
      }
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: text.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: text),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              color: text,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
