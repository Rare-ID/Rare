import {
  type CanActivate,
  type ExecutionContext,
  Inject,
  Injectable,
  Module,
} from "@nestjs/common";

import type { RarePlatformKit } from "@rare-id/platform-kit-web";

export const RARE_PLATFORM_KIT = Symbol("RARE_PLATFORM_KIT");

@Injectable()
export class RareAuthGuard implements CanActivate {
  constructor(
    @Inject(RARE_PLATFORM_KIT) private readonly kit: RarePlatformKit,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest();
    const sessionToken = String(req.headers.authorization ?? "").replace(
      /^Bearer\s+/i,
      "",
    );
    if (!sessionToken) {
      return false;
    }
    try {
      await this.kit.verifyAction({
        sessionToken,
        action: String(req.body?.action ?? "request"),
        actionPayload: (req.body?.action_payload ?? {}) as Record<
          string,
          unknown
        >,
        nonce: String(req.body?.nonce ?? ""),
        issuedAt: Number(req.body?.issued_at ?? 0),
        expiresAt: Number(req.body?.expires_at ?? 0),
        signatureBySession: String(req.body?.signature_by_session ?? ""),
      });
      return true;
    } catch {
      return false;
    }
  }
}

@Module({})
export class RarePlatformKitModule {
  private constructor() {}

  static forRoot(kit: RarePlatformKit) {
    return {
      module: RarePlatformKitModule,
      providers: [
        {
          provide: RARE_PLATFORM_KIT,
          useValue: kit,
        },
        RareAuthGuard,
      ],
      exports: [RARE_PLATFORM_KIT, RareAuthGuard],
    };
  }
}
